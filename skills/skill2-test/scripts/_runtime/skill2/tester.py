from __future__ import annotations

import json
import re
import secrets
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .cases import CaseSuite
from .codex_runner import ExecutionResult, run_codex
from .models import Case, TestRun, TrialResult
from .scan import scan_path

Runner = Callable[..., ExecutionResult]
_REMOTE_WRITE_RE = re.compile(
    r"(?:git\s+push|gh\s+release\s+create|twine\s+upload|uv\s+publish|npm\s+publish)",
    re.I,
)


def run_test_suite(
    *,
    target: Path,
    suite: CaseSuite,
    output_root: Path,
    pack: bool,
    baseline: bool,
    trials_override: int | None,
    timeout: int,
    model: str | None,
    case_ids: tuple[str, ...] = (),
    resume: Path | None = None,
    max_failure_rate: float | None = None,
    min_trials_before_stop: int = 5,
    runner: Runner = run_codex,
) -> TestRun:
    target = target.expanduser().resolve()
    if not (target / "SKILL.md").is_file():
        raise ValueError(f"target skill missing SKILL.md: {target}")
    skill_dirs = _pack_skills(target) if pack else (target,)
    record = scan_path(target).skills[0]
    if resume:
        run_dir = resume.expanduser().resolve()
        run_id = run_dir.name
        results = list(_resume_results(run_dir, target.name, record.hash, suite.path))
    else:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        run_id = f"{timestamp}-{secrets.token_hex(4)}-{target.name}"
        run_dir = output_root.expanduser().resolve() / run_id
        results = []
    selected = [case for case in suite.cases if not case_ids or case.id in case_ids]
    missing = sorted(set(case_ids) - {case.id for case in selected})
    if missing:
        raise ValueError(f"unknown case ids: {', '.join(missing)}")
    completed = {(item.case_id, item.trial, item.mode) for item in results}
    stopped_early = False

    for case in selected:
        repetitions = trials_override or case.repetitions
        fixture = _fixture_path(suite, case)
        for trial in range(1, repetitions + 1):
            artifact_dir = run_dir / case.id / "with-skill" / str(trial)
            key = (case.id, trial, "with_skill")
            if key not in completed:
                execution = runner(
                    prompt=case.prompt,
                    skill_dirs=skill_dirs,
                    fixture=fixture,
                    artifact_dir=artifact_dir,
                    timeout=timeout,
                    model=model,
                )
                results.append(_judge(case, trial, "with_skill", execution, artifact_dir))
                completed.add(key)
                _write_checkpoint(run_dir, run_id, target, suite, record.hash, results)

            if baseline and case.expect_activation:
                baseline_dir = run_dir / case.id / "baseline" / str(trial)
                baseline_key = (case.id, trial, "baseline")
                if baseline_key not in completed:
                    baseline_execution = runner(
                        prompt=case.prompt,
                        skill_dirs=(),
                        fixture=fixture,
                        artifact_dir=baseline_dir,
                        timeout=timeout,
                        model=model,
                    )
                    results.append(
                        _judge(case, trial, "baseline", baseline_execution, baseline_dir)
                    )
                    completed.add(baseline_key)
                    _write_checkpoint(run_dir, run_id, target, suite, record.hash, results)

            if _should_stop(results, max_failure_rate, min_trials_before_stop):
                stopped_early = True
                break
        if stopped_early:
            break

    test_run = TestRun(
        run_id=run_id,
        skill=target.name,
        agent=suite.agent,
        skill_hash=record.hash,
        cases_path=suite.path,
        trials=tuple(results),
        complete=not stopped_early,
        stopped_early=stopped_early,
    )
    _write_run(run_dir, test_run)
    return test_run


def _write_checkpoint(
    run_dir: Path,
    run_id: str,
    target: Path,
    suite: CaseSuite,
    skill_hash: str,
    results: list[TrialResult],
) -> None:
    _write_run(
        run_dir,
        TestRun(
            run_id=run_id,
            skill=target.name,
            agent=suite.agent,
            skill_hash=skill_hash,
            cases_path=suite.path,
            trials=tuple(results),
            complete=False,
        ),
    )


def _write_run(run_dir: Path, test_run: TestRun) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    temporary = run_dir / "run.json.tmp"
    temporary.write_text(
        json.dumps(test_run.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(run_dir / "run.json")


def _resume_results(
    run_dir: Path, skill: str, skill_hash: str, cases_path: str
) -> tuple[TrialResult, ...]:
    path = run_dir / "run.json"
    if not path.is_file():
        raise ValueError(f"resume run missing run.json: {run_dir}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid resume run JSON: {path}: {exc}") from exc
    if payload.get("skill") != skill or payload.get("skill_hash") != skill_hash:
        raise ValueError("resume run skill or hash does not match target")
    if payload.get("cases_path") != cases_path:
        raise ValueError("resume run cases path does not match suite")
    trials = payload.get("trials")
    if not isinstance(trials, list):
        raise ValueError(f"resume run trials must be a list: {path}")
    restored = tuple(_trial_from_dict(item) for item in trials)
    return tuple(item for item in restored if item.status in {"pass", "baseline"})


def _trial_from_dict(item: object) -> TrialResult:
    if not isinstance(item, dict):
        raise ValueError("resume trial must be an object")
    return TrialResult(
        case_id=str(item.get("case_id", "")),
        trial=int(item.get("trial", 0)),
        mode=str(item.get("mode", "")),
        status=str(item.get("status", "")),
        activation_status=str(item.get("activation_status", "")),
        outcome_status=str(item.get("outcome_status", "")),
        activations=tuple(str(value) for value in item.get("activations", [])),
        activation_confidence={
            str(key): str(value)
            for key, value in dict(item.get("activation_confidence", {})).items()
        },
        exit_code=int(item.get("exit_code", 0)),
        duration_ms=int(item.get("duration_ms", 0)),
        assertions=tuple(item.get("assertions", [])),
        evidence=tuple(str(value) for value in item.get("evidence", [])),
        artifact_dir=str(item.get("artifact_dir", "")),
    )


def _should_stop(
    results: list[TrialResult], threshold: float | None, minimum: int
) -> bool:
    if threshold is None:
        return False
    relevant = [item for item in results if item.mode == "with_skill"]
    if len(relevant) < minimum:
        return False
    failures = sum(item.status in {"fail", "runner_error"} for item in relevant)
    return failures / len(relevant) >= threshold


def write_junit(test_run: TestRun, path: Path) -> None:
    failures = sum(trial.status in {"fail", "runner_error"} for trial in test_run.trials)
    suite = ET.Element(
        "testsuite",
        {
            "name": f"skill2.{test_run.skill}",
            "tests": str(len(test_run.trials)),
            "failures": str(failures),
        },
    )
    for trial in test_run.trials:
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": f"skill2.{test_run.skill}.{trial.mode}",
                "name": f"{trial.case_id}[{trial.trial}]",
                "time": f"{trial.duration_ms / 1000:.3f}",
            },
        )
        if trial.status in {"fail", "runner_error"}:
            failure = ET.SubElement(case, "failure", {"message": trial.activation_status})
            failure.text = "\n".join(trial.evidence)
        output = ET.SubElement(case, "system-out")
        output.text = json.dumps(trial.to_dict(), ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def evaluate_assertions(
    assertions: tuple[dict[str, Any], ...], execution: ExecutionResult
) -> tuple[dict[str, Any], ...]:
    results: list[dict[str, Any]] = []
    workspace = Path(execution.workspace)
    for assertion in assertions:
        assertion_type = str(assertion.get("type") or "")
        passed = False
        detail = ""
        if assertion_type == "contains":
            value = str(assertion.get("value") or "")
            passed = value in execution.final_message
            detail = value
        elif assertion_type == "contains_any":
            values = [str(value) for value in assertion.get("values") or []]
            passed = any(value in execution.final_message for value in values)
            detail = ", ".join(values)
        elif assertion_type == "contains_all":
            values = [str(value) for value in assertion.get("values") or []]
            passed = bool(values) and all(value in execution.final_message for value in values)
            detail = ", ".join(values)
        elif assertion_type == "contains_groups":
            groups = [
                [str(value) for value in group]
                for group in assertion.get("groups") or []
                if isinstance(group, list)
            ]
            passed = bool(groups) and all(
                any(value in execution.final_message for value in group) for group in groups
            )
            detail = " | ".join("/".join(group) for group in groups)
        elif assertion_type == "not_contains":
            value = str(assertion.get("value") or "")
            passed = value not in execution.final_message
            detail = value
        elif assertion_type == "regex":
            value = str(assertion.get("value") or "")
            passed, detail = _search_regex(value, execution.final_message, invert=False)
        elif assertion_type == "not_regex":
            value = str(assertion.get("value") or "")
            passed, detail = _search_regex(value, execution.final_message, invert=True)
        elif assertion_type == "file_exists":
            value = str(assertion.get("path") or "")
            passed = (workspace / value).is_file()
            detail = value
        elif assertion_type == "file_contains":
            value = str(assertion.get("path") or "")
            expected = str(assertion.get("value") or "")
            path = workspace / value
            passed = path.is_file() and expected in path.read_text(encoding="utf-8")
            detail = f"{value}: {expected}"
        elif assertion_type == "exit_code":
            expected_code = int(assertion.get("value", 0))
            passed = execution.exit_code == expected_code
            detail = str(expected_code)
        elif assertion_type == "tool_contains":
            value = str(assertion.get("value") or "")
            passed = any(value in command for command in execution.commands)
            detail = value
        elif assertion_type == "no_remote_write":
            passed = not any(_REMOTE_WRITE_RE.search(command) for command in execution.commands)
            detail = "no push/release/upload commands"
        elif assertion_type == "no_file_changes":
            passed = not execution.changed_files
            detail = ", ".join(execution.changed_files)
        elif assertion_type == "json_equals":
            passed, detail = _assert_json_equals(
                workspace,
                path=str(assertion.get("path") or ""),
                pointer=str(assertion.get("pointer") or ""),
                expected=assertion.get("value"),
            )
        elif assertion_type == "max_lines":
            passed, detail = _assert_max_lines(
                execution.final_message, assertion.get("value")
            )
        else:
            detail = f"unknown assertion type: {assertion_type}"
        results.append(
            {
                "type": assertion_type,
                "passed": passed,
                "detail": detail,
            }
        )
    return tuple(results)


def _assert_max_lines(final_message: str, raw_value: Any) -> tuple[bool, str]:
    limit = _positive_int(raw_value)
    if limit is None:
        return False, f"invalid max_lines value: {raw_value!r}"
    non_empty = sum(1 for line in final_message.splitlines() if line.strip())
    return non_empty <= limit, f"{non_empty} <= {limit}"


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            number = int(text)
            return number if number > 0 else None
        return None
    return None


def _search_regex(pattern: str, text: str, *, invert: bool) -> tuple[bool, str]:
    try:
        matched = re.search(pattern, text, re.S) is not None
    except re.error as exc:
        return False, f"invalid regex: {pattern} ({exc})"
    if invert:
        return not matched, pattern
    return matched, pattern


def _assert_json_equals(
    workspace: Path, *, path: str, pointer: str, expected: Any
) -> tuple[bool, str]:
    if not path:
        return False, "json_equals missing path"
    workspace_root = workspace.resolve()
    target = (workspace_root / path).resolve()
    try:
        target.relative_to(workspace_root)
    except ValueError:
        return False, f"json_equals path escapes workspace: {path}"
    if not target.is_file():
        return False, f"missing file: {path}"
    try:
        text = target.read_text(encoding="utf-8")
        document = json.loads(text)
    except UnicodeDecodeError as exc:
        return False, f"invalid json encoding {path}: {exc}"
    except json.JSONDecodeError as exc:
        return False, f"invalid json {path}: {exc}"
    try:
        actual = _resolve_json_pointer(document, pointer)
    except ValueError as exc:
        return False, str(exc)
    if actual == expected:
        return True, f"{path}{pointer}"
    return False, f"{path}{pointer}: expected {expected!r}, got {actual!r}"


def _resolve_json_pointer(document: Any, pointer: str) -> Any:
    if pointer in {"", "#"}:
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid pointer (must start with /): {pointer}")
    current: Any = document
    for raw_token in pointer.split("/")[1:]:
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise ValueError(f"pointer missing key {token!r} at {pointer}")
            current = current[token]
            continue
        if isinstance(current, list):
            if not token.isdigit():
                raise ValueError(f"pointer non-index {token!r} on list at {pointer}")
            index = int(token)
            if index >= len(current):
                raise ValueError(f"pointer index {index} out of range at {pointer}")
            current = current[index]
            continue
        raise ValueError(f"pointer cannot descend into {type(current).__name__} at {pointer}")
    return current


def _judge(
    case: Case,
    trial: int,
    mode: str,
    execution: ExecutionResult,
    artifact_dir: Path,
) -> TrialResult:
    assertion_results = evaluate_assertions(case.assertions, execution)
    if mode == "baseline":
        activation_status = "not_checked"
        outcome_status = (
            "outcome_pass"
            if assertion_results and all(item["passed"] for item in assertion_results)
            else "outcome_fail"
            if assertion_results
            else "not_checked"
        )
        status = "baseline" if execution.error is None else "runner_error"
    else:
        activation_status = _activation_status(case, execution)
        outcome_status = (
            "outcome_pass"
            if assertion_results and all(item["passed"] for item in assertion_results)
            else "outcome_fail"
            if assertion_results
            else "not_checked"
        )
        if execution.error:
            status = "runner_error"
        elif activation_status in {"activation_gap", "false_positive"}:
            status = "fail"
        elif outcome_status == "outcome_fail":
            status = "fail"
        else:
            status = "pass"
    evidence = list(execution.evidence)
    if execution.error:
        evidence.append(execution.error)
    return TrialResult(
        case_id=case.id,
        trial=trial,
        mode=mode,
        status=status,
        activation_status=activation_status,
        outcome_status=outcome_status,
        activations=tuple(sorted(execution.activations)),
        activation_confidence=dict(sorted(execution.activations.items())),
        exit_code=execution.exit_code,
        duration_ms=execution.duration_ms,
        assertions=assertion_results,
        evidence=tuple(evidence),
        artifact_dir=str(artifact_dir),
    )


def _activation_status(case: Case, execution: ExecutionResult) -> str:
    forbidden = set(case.expect_not_activation) & set(execution.activations)
    if forbidden:
        return "false_positive"
    if case.expect_activation:
        return (
            "activation_pass"
            if case.expect_activation in execution.activations
            else "activation_gap"
        )
    return "activation_pass" if case.expect_not_activation else "not_checked"


def _pack_skills(target: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (path for path in target.parent.iterdir() if (path / "SKILL.md").is_file()),
            key=lambda path: path.name,
        )
    )


def _fixture_path(suite: CaseSuite, case: Case) -> Path | None:
    if not case.fixture:
        return None
    fixture = (Path(suite.path).parent / case.fixture).resolve()
    if not fixture.is_dir():
        raise ValueError(f"fixture not found: {fixture}")
    return fixture
