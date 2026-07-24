from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .models import SCHEMA_VERSION, Issue, LintResult, ScanResult, Severity

_SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_SARIF_LEVEL = {
    Severity.ERROR: "error",
    Severity.WARN: "warning",
    Severity.ADVICE: "note",
}


def _add_output_args(parser: argparse.ArgumentParser, *, default_path: str = "skills") -> None:
    parser.add_argument("path", nargs="?", default=default_path, help="input path")
    parser.add_argument(
        "--format",
        choices=("text", "json", "sarif"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--json",
        action="store_const",
        const="json",
        dest="format",
        help="alias for --format json",
    )


def _cmd_scaffold(args: argparse.Namespace) -> int:
    if args.kind == "skill":
        from .scaffold import scaffold_skill

        created = scaffold_skill(
            args.name,
            Path(args.output_dir or "skills"),
            args.description,
        )
    else:
        from .package import scaffold_skill_repo

        try:
            created = scaffold_skill_repo(args.name, Path(args.output_dir or "."))
        except (FileExistsError, ValueError) as exc:
            print(f"skill2 scaffold: {exc}", file=sys.stderr)
            return 2
    for path in created:
        print(path)
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    from .scan import scan_path

    result = scan_path(Path(args.path))
    if args.format == "json":
        _print_json(result.to_dict())
    elif args.format == "sarif":
        _print_json(_to_sarif((), scan=result))
    else:
        _print_scan_text(result)
    return 0


def _cmd_lint(args: argparse.Namespace) -> int:
    from .lint import lint_scan
    from .scan import scan_path

    result = lint_scan(scan_path(Path(args.path)))
    if args.format == "json":
        _print_json(result.to_dict())
    elif args.format == "sarif":
        _print_json(_to_sarif(result.issues))
    else:
        _print_lint_text(result)
    return 1 if result.has_errors else 0


def _cmd_test(args: argparse.Namespace) -> int:
    from .cases import load_case_suite
    from .claude_runner import run_claude
    from .codex_runner import run_codex
    from .tester import run_test_suite, write_junit

    try:
        suite = load_case_suite(Path(args.cases))
        if suite.agent != args.agent:
            raise ValueError(f"case agent `{suite.agent}` does not match `--agent {args.agent}`")
        result = run_test_suite(
            target=Path(args.skill),
            suite=suite,
            output_root=Path(args.out),
            pack=args.pack,
            baseline=args.baseline,
            trials_override=args.trials,
            timeout=args.timeout,
            model=args.model,
            case_ids=tuple(args.case),
            resume=Path(args.resume) if args.resume else None,
            max_failure_rate=args.max_failure_rate,
            min_trials_before_stop=args.min_trials_before_stop,
            runner=run_codex if args.agent == "codex" else run_claude,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"skill2 test: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _print_json(result.to_dict())
    else:
        for trial in result.trials:
            print(
                f"{trial.status} {trial.case_id} trial={trial.trial} mode={trial.mode} "
                f"activation={trial.activation_status} outcome={trial.outcome_status}"
            )
        print(f"run={result.run_id} passed={str(result.passed).lower()}")
    if args.junit:
        write_junit(result, Path(args.junit))
    return 0 if result.passed else 1


def _cmd_package_check(args: argparse.Namespace) -> int:
    from .package import package_check, publish_preflight

    result = publish_preflight(Path(args.path)) if args.publish else package_check(Path(args.path))
    if args.format == "json":
        _print_json(result.to_dict())
    elif args.format == "sarif":
        _print_json(_to_sarif(result.issues))
    else:
        for issue in result.issues:
            print(f"{issue.severity.value} {issue.rule_id} {issue.path}: {issue.message}")
        print(f"issues={len(result.issues)}")
    return 1 if result.has_errors else 0


def _usage_from_args(args: argparse.Namespace):
    from .usage import parse_usage

    return parse_usage(
        Path(args.skills),
        codex_root=_optional_root(args.codex),
        claude_root=_optional_root(getattr(args, "claude", None)),
    )


def _optional_root(value: str | None) -> Path | None:
    if value is None or value == "" or value == "-":
        return None
    return Path(value)


def _cmd_usage(args: argparse.Namespace) -> int:
    result = _usage_from_args(args)
    if args.json:
        _print_json(result.to_dict())
    else:
        for event in result.events:
            print(
                f"{event.timestamp}\t{event.harness}\t{event.skill}\t{event.category}\t"
                f"{event.confidence}\t{event.session}"
            )
        print(f"events={result.summary['total_events']}")
    return 0


def _cmd_suggest(args: argparse.Namespace) -> int:
    from .scan import scan_path
    from .suggest import build_suggestions

    try:
        scan = scan_path(Path(args.skills))
        usage = _usage_from_args(args)
        test_runs = _load_test_runs(Path(args.tests))
        result = build_suggestions(scan, usage, test_runs)
    except (OSError, ValueError) as exc:
        print(f"skill2 suggest: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _print_json(result.to_dict())
    else:
        for item in result.suggestions:
            print(f"{item.action}\t{item.target}\t{item.reason}")
        print(f"suggestions={len(result.suggestions)}")
    return 0


def _cmd_visualize(args: argparse.Namespace) -> int:
    from .report import build_report, render_terminal
    from .scan import scan_path
    from .suggest import build_suggestions

    try:
        scan = scan_path(Path(args.skills))
        usage = _usage_from_args(args)
        test_runs = _load_test_runs(Path(args.tests))
        report = build_report(scan, usage, test_runs)
        suggestions = build_suggestions(scan, usage, test_runs).to_dict()["suggestions"]
        report["suggestions"] = suggestions
    except (OSError, ValueError) as exc:
        print(f"skill2 visualize: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _print_json(report)
    else:
        print(render_terminal(report, suggestions))
    return 0


def _load_test_runs(root: Path) -> tuple[dict[str, Any], ...]:
    resolved = root.expanduser()
    if not resolved.exists():
        return ()
    paths = (resolved,) if resolved.is_file() else tuple(sorted(resolved.rglob("run.json")))
    runs: list[dict[str, Any]] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid test run JSON: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"test run must be a JSON object: {path}")
        runs.append(payload)
    return tuple(runs)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return parsed


def _rate(value: str) -> float:
    parsed = float(value)
    if not 0 < parsed <= 1:
        raise argparse.ArgumentTypeError("must be > 0 and <= 1")
    return parsed


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_scan_text(result: ScanResult) -> None:
    for skill in result.skills:
        print(
            f"{skill.name} {skill.path} tokens={skill.body_tokens} "
            f"references={len(skill.references)} scripts={len(skill.scripts)} "
            f"assets={len(skill.assets)} scope={skill.scope}"
        )
    print(f"scanned={len(result.skills)}")


def _print_lint_text(result: LintResult) -> None:
    for issue in result.issues:
        print(f"{issue.severity.value} {issue.rule_id} {issue.path}: {issue.message}")
    print(f"checked={result.checked} issues={len(result.issues)}")


def _to_sarif(issues: tuple[Issue, ...], *, scan: ScanResult | None = None) -> dict[str, Any]:
    rule_ids = sorted({issue.rule_id for issue in issues})
    run: dict[str, Any] = {
        "tool": {
            "driver": {
                "name": "skill2",
                "informationUri": "https://github.com/blackblue-labs/skill2",
                "rules": [{"id": rule_id} for rule_id in rule_ids],
            }
        },
        "results": [_sarif_result(issue) for issue in issues],
        "properties": {"skill2_schema_version": SCHEMA_VERSION},
    }
    if scan is not None:
        run["properties"]["scan"] = scan.to_dict()
    return {"$schema": _SARIF_SCHEMA, "version": "2.1.0", "runs": [run]}


def _sarif_result(issue: Issue) -> dict[str, Any]:
    return {
        "ruleId": issue.rule_id,
        "level": _SARIF_LEVEL[issue.severity],
        "message": {"text": issue.message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": _path_uri(issue.path)},
                }
            }
        ],
    }


def _path_uri(value: str) -> str:
    path = Path(value)
    return path.as_uri() if path.is_absolute() else path.as_posix()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill2", add_help=False)
    parser.add_argument(
        "-h", "--help", action="help", help="show this help message and exit"
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"skill2 {__version__}",
        help="print version and exit",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scaffold = sub.add_parser("scaffold", help="create skill scaffolds")
    scaffold.add_argument("kind", choices=["skill", "skill-repo"])
    scaffold.add_argument("name")
    scaffold.add_argument("-o", "--output-dir", default=None)
    scaffold.add_argument("--description", default=None)
    scaffold.set_defaults(func=_cmd_scaffold)

    scan = sub.add_parser("scan", help="scan skill inventory")
    _add_output_args(scan)
    scan.set_defaults(func=_cmd_scan)

    lint = sub.add_parser("lint", help="lint scanned skills")
    _add_output_args(lint)
    lint.set_defaults(func=_cmd_lint)

    test = sub.add_parser("test", help="run isolated skill cases")
    test.add_argument("skill", help="target skill directory")
    test.add_argument("--agent", choices=["codex", "claude"], default="codex")
    test.add_argument("--cases", required=True, help="case YAML file")
    test.add_argument("--isolate", action="store_true", default=True)
    test.add_argument("--pack", action="store_true", help="install sibling skills too")
    test.add_argument("--baseline", action="store_true", help="run positive cases without skills")
    test.add_argument("--case", action="append", default=[], help="run one case id; repeatable")
    test.add_argument("--trials", type=_positive_int, default=None, help="override repetitions")
    test.add_argument("--timeout", type=_positive_int, default=180, help="seconds per trial")
    test.add_argument("--model", default=None)
    test.add_argument("--out", default=".skill2/test-runs")
    test.add_argument("--junit", default=None)
    test.add_argument("--resume", default=None, help="resume a prior run directory")
    test.add_argument("--max-failure-rate", type=_rate, default=None)
    test.add_argument("--min-trials-before-stop", type=_positive_int, default=5)
    test.add_argument("--json", action="store_true")
    test.set_defaults(func=_cmd_test)

    package = sub.add_parser("package-check", help="validate an installable skill repo")
    _add_output_args(package, default_path=".")
    package.set_defaults(func=_cmd_package_check, publish=False)

    publish = sub.add_parser("publish-check", help="run release preflight without remote writes")
    _add_output_args(publish, default_path=".")
    publish.set_defaults(func=_cmd_package_check, publish=True)

    usage = sub.add_parser("usage", help="parse local Codex/Claude skill usage evidence")
    usage.add_argument("--codex", default="~/.codex", help="Codex root; '-' to skip")
    usage.add_argument("--claude", default="~/.claude", help="Claude root; '-' to skip")
    usage.add_argument("--skills", default="skills")
    usage.add_argument("--json", action="store_true")
    usage.set_defaults(func=_cmd_usage)

    suggest = sub.add_parser("suggest", help="derive read-only skill maintenance suggestions")
    suggest.add_argument("--codex", default="~/.codex", help="Codex root; '-' to skip")
    suggest.add_argument("--claude", default="~/.claude", help="Claude root; '-' to skip")
    suggest.add_argument("--skills", default="skills")
    suggest.add_argument("--tests", default=".skill2/test-runs")
    suggest.add_argument("--json", action="store_true")
    suggest.set_defaults(func=_cmd_suggest)

    visualize = sub.add_parser("visualize", help="show skill library evidence in the terminal")
    visualize.add_argument("--codex", default="~/.codex", help="Codex root; '-' to skip")
    visualize.add_argument("--claude", default="~/.claude", help="Claude root; '-' to skip")
    visualize.add_argument("--skills", default="skills")
    visualize.add_argument("--tests", default=".skill2/test-runs")
    visualize.add_argument("--json", action="store_true")
    visualize.set_defaults(func=_cmd_visualize)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
