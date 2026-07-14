from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skill2.cases import load_case_suite
from skill2.claude_runner import run_claude
from skill2.codex_runner import ExecutionResult, detect_activations, run_codex
from skill2.tester import evaluate_assertions, run_test_suite

ROOT = Path(__file__).resolve().parents[1]
_SKILL2_HELP_MARKERS = (
    "scaffold",
    "scan",
    "lint",
    "test",
    "package-check",
    "publish-check",
    "usage",
    "suggest",
    "visualize",
)
_USER_LOCAL_BIN = str(Path.home() / ".local" / "bin")


class EvaluationTest(unittest.TestCase):
    def test_load_case_suite_normalizes_legacy_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.yaml"
            path.write_text(
                """skill: demo
agent: codex
defaults:
  repetitions: 3
cases:
  - name: Core trigger
    prompt: Build a demo skill
    expect_activation: demo
    assertions:
      - type: contains
        value: SKILL.md
""",
                encoding="utf-8",
            )
            suite = load_case_suite(path)
            self.assertEqual(suite.skill, "demo")
            self.assertEqual(suite.cases[0].id, "core-trigger")
            self.assertEqual(suite.cases[0].repetitions, 3)

    def test_detect_activation_from_exact_skill_path(self) -> None:
        skill_file = Path("/tmp/isolated/skills/demo/SKILL.md")
        events = (
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": f"sed -n 1,200p {skill_file}",
                },
            },
        )
        activations, evidence = detect_activations(events, {"demo": skill_file})
        self.assertEqual(activations, {"demo": "medium"})
        self.assertIn("exact SKILL.md read: demo", evidence)

    def test_scan_output_is_not_activation(self) -> None:
        skill_file = Path("/tmp/isolated/skills/demo/SKILL.md")
        events = (
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "find /tmp/isolated/skills -name SKILL.md",
                    "aggregated_output": str(skill_file),
                },
            },
        )
        activations, _ = detect_activations(events, {"demo": skill_file})
        self.assertEqual(activations, {})

    def test_assertions_use_output_workspace_and_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "result.txt").write_text("ready", encoding="utf-8")
            execution = ExecutionResult(
                exit_code=0,
                duration_ms=1,
                final_message="隔离 activation ready",
                events=(),
                commands=("skill2 lint skills",),
                activations={},
                evidence=(),
                workspace=str(workspace),
                changed_files=("result.txt",),
            )
            assertions = (
                {"type": "contains", "value": "activation"},
                {"type": "contains_all", "values": ["隔离", "ready"]},
                {"type": "contains_groups", "groups": [["隔离", "isolate"], ["ready"]]},
                {"type": "file_contains", "path": "result.txt", "value": "ready"},
                {"type": "tool_contains", "value": "skill2 lint"},
                {"type": "no_remote_write"},
            )
            results = evaluate_assertions(assertions, execution)
            self.assertTrue(all(item["passed"] for item in results), json.dumps(results))

    def test_not_regex_pass_and_fail(self) -> None:
        harness_skill = r"(?i)\b(?:codex|claude|opencode)\b[^\n]{0,40}\bskill\b"
        good = ExecutionResult(
            exit_code=0,
            duration_ms=1,
            final_message=(
                "agent: codex\n"
                "schema_version: 1\n"
                "skill: api-docs\n"
                "A harness-neutral API docs skill."
            ),
            events=(),
            commands=(),
            activations={},
            evidence=(),
            workspace="/tmp",
            changed_files=(),
        )
        passed = evaluate_assertions(({"type": "not_regex", "value": harness_skill},), good)
        self.assertTrue(passed[0]["passed"], json.dumps(passed))

        for sample in (
            "Use this Claude Code skill for API docs.",
            "A Codex-specific skill for OpenAPI.",
            "Ship a **OpenCode** agent skill now.",
        ):
            bad = ExecutionResult(
                exit_code=0,
                duration_ms=1,
                final_message=sample,
                events=(),
                commands=(),
                activations={},
                evidence=(),
                workspace="/tmp",
                changed_files=(),
            )
            failed = evaluate_assertions(({"type": "not_regex", "value": harness_skill},), bad)
            self.assertFalse(failed[0]["passed"], f"{sample!r} -> {json.dumps(failed)}")

    def test_regex_and_not_regex_invalid_pattern_do_not_crash(self) -> None:
        execution = ExecutionResult(
            exit_code=0,
            duration_ms=1,
            final_message="ready",
            events=(),
            commands=(),
            activations={},
            evidence=(),
            workspace="/tmp",
            changed_files=(),
        )
        results = evaluate_assertions(
            (
                {"type": "regex", "value": "("},
                {"type": "not_regex", "value": "["},
            ),
            execution,
        )
        self.assertEqual(len(results), 2)
        self.assertFalse(results[0]["passed"])
        self.assertFalse(results[1]["passed"])
        self.assertIn("invalid regex", results[0]["detail"])
        self.assertIn("invalid regex", results[1]["detail"])

    def test_max_lines_pass(self) -> None:
        message = "\n".join(
            [
                "summary: 3 skills",
                "top: a 3",
                "top: b 1",
                "",
                "  ",
                "evidence: SKILL.md reads only",
            ]
        )
        execution = ExecutionResult(
            exit_code=0,
            duration_ms=1,
            final_message=message,
            events=(),
            commands=(),
            activations={},
            evidence=(),
            workspace="/tmp",
            changed_files=(),
        )
        results = evaluate_assertions(({"type": "max_lines", "value": 20},), execution)
        self.assertTrue(results[0]["passed"], json.dumps(results))
        self.assertEqual(results[0]["detail"], "4 <= 20")

        string_limit = evaluate_assertions(({"type": "max_lines", "value": "4"},), execution)
        self.assertTrue(string_limit[0]["passed"], json.dumps(string_limit))

    def test_max_lines_fail(self) -> None:
        message = "\n".join(f"line {index}" for index in range(21))
        execution = ExecutionResult(
            exit_code=0,
            duration_ms=1,
            final_message=message,
            events=(),
            commands=(),
            activations={},
            evidence=(),
            workspace="/tmp",
            changed_files=(),
        )
        results = evaluate_assertions(({"type": "max_lines", "value": 20},), execution)
        self.assertFalse(results[0]["passed"], json.dumps(results))
        self.assertEqual(results[0]["detail"], "21 <= 20")

    def test_max_lines_invalid_value_fails_safely(self) -> None:
        execution = ExecutionResult(
            exit_code=0,
            duration_ms=1,
            final_message="one\ntwo",
            events=(),
            commands=(),
            activations={},
            evidence=(),
            workspace="/tmp",
            changed_files=(),
        )
        for value in (0, -1, None, "", "abc", "20.5", True, False, 3.14, []):
            results = evaluate_assertions(({"type": "max_lines", "value": value},), execution)
            self.assertEqual(len(results), 1)
            self.assertFalse(results[0]["passed"], f"value={value!r} -> {json.dumps(results)}")
            self.assertIn("invalid max_lines value", results[0]["detail"])

    def test_json_equals_pass_and_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "chart.json").write_text(
                json.dumps(
                    {
                        "title": "Top bars",
                        "bars": [
                            {"label": "Beta", "value": 30},
                            {"label": "Delta", "value": 25},
                            {"label": "Gamma", "value": 20},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            execution = ExecutionResult(
                exit_code=0,
                duration_ms=1,
                final_message="done",
                events=(),
                commands=(),
                activations={},
                evidence=(),
                workspace=str(workspace),
                changed_files=("chart.json",),
            )
            expected_bars = [
                {"label": "Beta", "value": 30},
                {"label": "Delta", "value": 25},
                {"label": "Gamma", "value": 20},
            ]
            passed = evaluate_assertions(
                (
                    {
                        "type": "json_equals",
                        "path": "chart.json",
                        "pointer": "/bars",
                        "value": expected_bars,
                    },
                ),
                execution,
            )
            self.assertTrue(passed[0]["passed"], json.dumps(passed))

            nested = evaluate_assertions(
                (
                    {
                        "type": "json_equals",
                        "path": "chart.json",
                        "pointer": "/bars/0/label",
                        "value": "Beta",
                    },
                ),
                execution,
            )
            self.assertTrue(nested[0]["passed"], json.dumps(nested))

            wrong = evaluate_assertions(
                (
                    {
                        "type": "json_equals",
                        "path": "chart.json",
                        "pointer": "/bars",
                        "value": [{"label": "Alpha", "value": 1}],
                    },
                ),
                execution,
            )
            self.assertFalse(wrong[0]["passed"], json.dumps(wrong))
            self.assertIn("/bars", wrong[0]["detail"])

    def test_json_equals_malformed_and_missing_pointer_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "bad.json").write_text("{not-json", encoding="utf-8")
            (workspace / "ok.json").write_text('{"a": {"b": 1}}', encoding="utf-8")
            execution = ExecutionResult(
                exit_code=0,
                duration_ms=1,
                final_message="done",
                events=(),
                commands=(),
                activations={},
                evidence=(),
                workspace=str(workspace),
                changed_files=(),
            )
            results = evaluate_assertions(
                (
                    {
                        "type": "json_equals",
                        "path": "missing.json",
                        "pointer": "/x",
                        "value": 1,
                    },
                    {
                        "type": "json_equals",
                        "path": "bad.json",
                        "pointer": "/x",
                        "value": 1,
                    },
                    {
                        "type": "json_equals",
                        "path": "ok.json",
                        "pointer": "/a/missing",
                        "value": 1,
                    },
                    {
                        "type": "json_equals",
                        "path": "ok.json",
                        "pointer": "/a/b/0",
                        "value": 1,
                    },
                ),
                execution,
            )
            self.assertEqual(len(results), 4)
            for item in results:
                self.assertFalse(item["passed"], json.dumps(item))
                self.assertIsInstance(item["detail"], str)
                self.assertTrue(item["detail"])
            self.assertIn("missing.json", results[0]["detail"])
            self.assertTrue(
                "invalid json" in results[1]["detail"].lower()
                or "json" in results[1]["detail"].lower()
            )
            self.assertTrue(
                "pointer" in results[2]["detail"].lower()
                or "missing" in results[2]["detail"].lower()
                or "/a/missing" in results[2]["detail"]
            )

    def test_json_equals_rejects_workspace_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            (root / "secret.json").write_text('{"value": 7}', encoding="utf-8")
            execution = ExecutionResult(
                exit_code=0,
                duration_ms=1,
                final_message="done",
                events=(),
                commands=(),
                activations={},
                evidence=(),
                workspace=str(workspace),
                changed_files=(),
            )
            result = evaluate_assertions(
                (
                    {
                        "type": "json_equals",
                        "path": "../secret.json",
                        "pointer": "/value",
                        "value": 7,
                    },
                ),
                execution,
            )
            self.assertFalse(result[0]["passed"], json.dumps(result))
            self.assertIn("workspace", result[0]["detail"].lower())

    def test_three_bar_analysis_fixture_case_loads(self) -> None:
        suite = load_case_suite(ROOT / "tests/fixtures/three-bar-analysis-case.yaml")
        self.assertEqual(suite.skill, "three-bar-analysis")
        self.assertEqual(len(suite.cases), 1)
        case = suite.cases[0]
        self.assertEqual(case.expect_activation, "three-bar-analysis")
        self.assertEqual(case.repetitions, 1)
        self.assertEqual(case.assertions[0]["type"], "json_equals")
        self.assertEqual(case.assertions[0]["path"], "chart.json")
        self.assertEqual(case.assertions[0]["pointer"], "/bars")
        self.assertEqual(
            case.assertions[0]["value"],
            [
                {"label": "Beta", "value": 30},
                {"label": "Delta", "value": 25},
                {"label": "Gamma", "value": 20},
            ],
        )
        prompt_lower = case.prompt.lower()
        self.assertNotIn("top 3", prompt_lower)
        self.assertNotIn("top-3", prompt_lower)
        self.assertNotIn("top three", prompt_lower)

    def test_all_repository_case_files_parse(self) -> None:
        suites = [load_case_suite(path) for path in sorted((ROOT / "cases").glob("*.yaml"))]
        self.assertEqual(len(suites), 6)
        self.assertEqual(sum(len(suite.cases) for suite in suites), 33)

    def test_runner_checkpoints_and_skips_completed_trials_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _write_demo_skill(root)
            suite = _write_demo_suite(root, repetitions=2)
            calls = []

            def runner(**kwargs):
                calls.append(kwargs["artifact_dir"])
                workspace = kwargs["artifact_dir"] / "workspace"
                workspace.mkdir(parents=True)
                return ExecutionResult(
                    exit_code=0,
                    duration_ms=1,
                    final_message="ready",
                    events=(),
                    commands=(),
                    activations={"demo": "medium"},
                    evidence=(),
                    workspace=str(workspace),
                    changed_files=(),
                )

            first = run_test_suite(
                target=skill,
                suite=suite,
                output_root=root / "runs",
                pack=False,
                baseline=False,
                trials_override=None,
                timeout=1,
                model=None,
                runner=runner,
            )
            run_dir = root / "runs" / first.run_id
            self.assertEqual(len(first.trials), 2)
            self.assertTrue((run_dir / "run.json").is_file())

            resumed = run_test_suite(
                target=skill,
                suite=suite,
                output_root=root / "runs",
                pack=False,
                baseline=False,
                trials_override=None,
                timeout=1,
                model=None,
                resume=run_dir,
                runner=runner,
            )

            self.assertEqual(len(resumed.trials), 2)
            self.assertEqual(len(calls), 2)

            another = run_test_suite(
                target=skill,
                suite=suite,
                output_root=root / "runs",
                pack=False,
                baseline=False,
                trials_override=1,
                timeout=1,
                model=None,
                runner=runner,
            )
            self.assertNotEqual(first.run_id, another.run_id)

    def test_runner_stops_after_failure_rate_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _write_demo_skill(root)
            suite = _write_demo_suite(root, repetitions=3)

            def runner(**kwargs):
                workspace = kwargs["artifact_dir"] / "workspace"
                workspace.mkdir(parents=True)
                return ExecutionResult(
                    exit_code=0,
                    duration_ms=1,
                    final_message="missed",
                    events=(),
                    commands=(),
                    activations={},
                    evidence=(),
                    workspace=str(workspace),
                    changed_files=(),
                )

            result = run_test_suite(
                target=skill,
                suite=suite,
                output_root=root / "runs",
                pack=False,
                baseline=False,
                trials_override=None,
                timeout=1,
                model=None,
                max_failure_rate=0.5,
                min_trials_before_stop=1,
                runner=runner,
            )

            self.assertEqual(len(result.trials), 1)
            self.assertEqual(result.trials[0].status, "fail")
            self.assertFalse(result.complete)
            self.assertTrue(result.stopped_early)

    def test_claude_runner_uses_isolated_skill_directory_with_fake_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _write_demo_skill(root)
            fake = root / "claude"
            fake.write_text(
                "#!/bin/sh\n"
                "set -eu\n"
                "skill=$(find \"$HOME/.claude/skills\" -name SKILL.md | head -1)\n"
                "printf '{\"type\":\"assistant\",\"message\":{\"content\":['\n"
                "printf '{\"type\":\"tool_use\",\"name\":\"Read\",'\n"
                "printf '\"input\":{\"file_path\":\"%s\"}}]}}\\n' \"$skill\"\n"
                "printf '{\"type\":\"result\",\"result\":\"ready\"}\\n'\n"
                "printf ready > ready.txt\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            with patch.dict(
                os.environ,
                {
                    "SKILL2_CLAUDE_BIN": str(fake),
                    "SKILL2_ALLOW_UNGUARDED": "1",
                },
            ):
                result = run_claude(
                    prompt="Run demo.",
                    skill_dirs=(skill,),
                    fixture=None,
                    artifact_dir=root / "artifacts",
                    timeout=10,
                    model=None,
                )
            self.assertEqual(result.exit_code, 0, result.error)
            self.assertEqual(result.activations, {"demo": "medium"})
            self.assertEqual(result.final_message, "ready")
            self.assertIn("ready.txt", result.changed_files)

    def test_claude_runner_exposes_skill2_cli_without_user_local_bin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _write_demo_skill(root)
            fake = root / "claude"
            fake.write_text(_fake_claude_skill2_probe_script(), encoding="utf-8")
            fake.chmod(0o755)
            artifacts = root / "artifacts"
            with patch.dict(
                os.environ,
                {
                    "SKILL2_CLAUDE_BIN": str(fake),
                    "SKILL2_ALLOW_UNGUARDED": "1",
                },
            ):
                result = run_claude(
                    prompt="Probe skill2 CLI.",
                    skill_dirs=(skill,),
                    fixture=None,
                    artifact_dir=artifacts,
                    timeout=30,
                    model=None,
                )
            self.assertEqual(result.exit_code, 0, result.error)
            _assert_skill2_cli_probe(self, Path(result.workspace), artifacts / "manifest.json")

    def test_codex_runner_exposes_skill2_cli_without_user_local_bin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _write_demo_skill(root)
            fake = root / "codex"
            fake.write_text(_fake_codex_skill2_probe_script(), encoding="utf-8")
            fake.chmod(0o755)
            host_codex = root / "host-codex"
            host_codex.mkdir()
            (host_codex / "auth.json").write_text("{}", encoding="utf-8")
            artifacts = root / "artifacts"
            with patch.dict(
                os.environ,
                {
                    "SKILL2_CODEX_BIN": str(fake),
                    "CODEX_HOME": str(host_codex),
                    "SKILL2_ALLOW_UNGUARDED": "1",
                    "PATH": "/usr/bin:/bin",
                },
            ):
                result = run_codex(
                    prompt="Probe skill2 CLI.",
                    skill_dirs=(skill,),
                    fixture=None,
                    artifact_dir=artifacts,
                    timeout=30,
                    model=None,
                )
            self.assertEqual(result.exit_code, 0, result.error)
            _assert_skill2_cli_probe(self, Path(result.workspace), artifacts / "manifest.json")


def _fake_claude_skill2_probe_script() -> str:
    return """#!/bin/sh
set -eu
printf '%s\\n' "$PATH" > path.txt
command -v skill2 > skill2-which.txt
skill2_bin=$(command -v skill2)
sed -n '1,40p' "$skill2_bin" > skill2-wrapper.txt
skill2 --help > skill2-help.txt
printf '{\\\"type\\\":\\\"result\\\",\\\"result\\\":\\\"skill2-ok\\\"}\\n'
"""


def _fake_codex_skill2_probe_script() -> str:
    return """#!/bin/sh
set -eu
if [ "${1:-}" = "--version" ]; then
  printf 'codex-fake 0.0.0\n'
  exit 0
fi
last=""
prev=""
for arg in "$@"; do
  if [ "$prev" = "--output-last-message" ]; then
    last="$arg"
  fi
  prev="$arg"
done
printf '%s\\n' "$PATH" > path.txt
command -v skill2 > skill2-which.txt
skill2_bin=$(command -v skill2)
sed -n '1,40p' "$skill2_bin" > skill2-wrapper.txt
skill2 --help > skill2-help.txt
if [ -n "$last" ]; then
  printf 'skill2-ok\\n' > "$last"
fi
printf '%s\\n' \
  '{"type":"item.completed","item":{"type":"command_execution","command":"skill2 --help"}}'
"""


def _assert_skill2_cli_probe(
    test: unittest.TestCase, workspace: Path, manifest_path: Path
) -> None:
    help_text = (workspace / "skill2-help.txt").read_text(encoding="utf-8")
    test.assertIn("usage: skill2", help_text)
    for marker in _SKILL2_HELP_MARKERS:
        test.assertIn(marker, help_text)

    path_text = (workspace / "path.txt").read_text(encoding="utf-8").strip()
    path_parts = [part for part in path_text.split(os.pathsep) if part]
    test.assertTrue(path_parts, "PATH should be non-empty")
    test.assertTrue(
        all(".local/bin" not in part for part in path_parts),
        f"PATH must not include user local bin entries: {path_text}",
    )
    test.assertNotIn(_USER_LOCAL_BIN, path_parts)
    test.assertNotIn(str((Path.home() / ".local" / "bin").resolve()), path_parts)

    which_text = (workspace / "skill2-which.txt").read_text(encoding="utf-8").strip()
    test.assertTrue(which_text, "skill2 missing from isolated PATH")
    test.assertNotIn("/.local/bin/", which_text)
    test.assertTrue(which_text.endswith("/skill2"), which_text)
    test.assertEqual(path_parts[0], str(Path(which_text).parent))

    wrapper = (workspace / "skill2-wrapper.txt").read_text(encoding="utf-8")
    test.assertIn("PYTHONPATH=", wrapper)
    test.assertIn("skill2.cli", wrapper)
    test.assertIn(sys.executable, wrapper)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    isolation = manifest["isolation"]
    test.assertTrue(isolation["skill2_cli_available"])


def _write_demo_skill(root: Path) -> Path:
    skill = root / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        """---
name: demo
description: "Use when testing demo behavior."
---

# Demo

Return ready after reading this skill.
""",
        encoding="utf-8",
    )
    return skill


def _write_demo_suite(root: Path, repetitions: int):
    path = root / "cases.yaml"
    path.write_text(
        f"""schema_version: "1"
skill: demo
agent: codex
defaults:
  repetitions: {repetitions}
cases:
  - id: core
    prompt: "Run demo."
    expect_activation: demo
""",
        encoding="utf-8",
    )
    return load_case_suite(path)


if __name__ == "__main__":
    unittest.main()
