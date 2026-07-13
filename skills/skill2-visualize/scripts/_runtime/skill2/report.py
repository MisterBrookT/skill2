from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .models import SCHEMA_VERSION, ScanResult
from .usage import IndirectCategory, UsageResult

_DIRECT_MARK = "█"
_INDIRECT_MARK = "░"
_EMPTY_MARK = "·"
_BAR_WIDTH = 16


def build_report(
    scan: ScanResult,
    usage: UsageResult,
    test_runs: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Build compact, local-only evidence for terminal or JSON output."""
    events = tuple(_event(event) for event in usage.events)
    tests = _tests_by_skill(test_runs)
    by_skill: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in events:
        by_skill[event["skill"]].append(event)

    skills: list[dict[str, Any]] = []
    for skill in scan.skills:
        skill_events = by_skill.get(skill.name, [])
        direct = [event for event in skill_events if event["category"] == "activation"]
        indirect = [
            event for event in skill_events if event["category"] in IndirectCategory
        ]
        test = tests.get(skill.name, {"total": 0, "passed": 0})
        skills.append(
            {
                "name": skill.name,
                "direct_calls": len(direct),
                "indirect_calls": len(indirect),
                "last_direct_call": max(
                    (event["timestamp"] for event in direct), default="never"
                ),
                "usage_categories": dict(
                    sorted(Counter(event["category"] for event in skill_events).items())
                ),
                "tests": test,
            }
        )
    skills.sort(
        key=lambda item: (-item["direct_calls"], -item["indirect_calls"], item["name"])
    )
    direct_calls = sum(item["direct_calls"] for item in skills)
    indirect_calls = sum(item["indirect_calls"] for item in skills)
    zero_direct = sum(item["direct_calls"] == 0 for item in skills)
    tested = sum(item["tests"]["total"] > 0 for item in skills)
    harnesses = usage.summary.get("by_harness") if isinstance(usage.summary, dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "skills": len(skills),
            "direct_calls": direct_calls,
            "indirect_calls": indirect_calls,
            "zero_direct": zero_direct,
            "tested_skills": tested,
            "by_harness": harnesses if isinstance(harnesses, dict) else {},
        },
        "skills": skills,
        "limits": [
            "Exact SKILL.md reads are usage evidence, not complete invocation history.",
            "Zero or low usage never authorizes deletion.",
            "Hooks and non-tool skill injection are not counted.",
        ],
    }


def render_terminal(
    report: dict[str, Any],
    suggestions: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None,
) -> str:
    summary = report["summary"]
    skills = report["skills"]
    harness = summary.get("by_harness") or {}
    harness_bits = (
        " · ".join(f"{name} {count}" for name, count in sorted(harness.items()))
        if harness
        else "no harness hits"
    )
    lines = [
        "Skill Library",
        (
            f"{summary['skills']} skills · {summary['direct_calls']} direct · "
            f"{summary.get('indirect_calls', 0)} indirect · "
            f"{summary['zero_direct']} zero-direct · {summary['tested_skills']} tested"
        ),
        f"sources: {harness_bits}",
        "",
    ]
    if not skills:
        lines.append("No scanned skills.")
    else:
        name_width = max(5, min(32, max(len(item["name"]) for item in skills)))
        lines.append(
            f"{'SKILL':<{name_width}}  {'D':>4}  {'I':>4}  {'LAST':<10}  {'TEST':<7}  USAGE"
        )
        max_total = max(
            (
                item["direct_calls"] + item.get("indirect_calls", 0)
                for item in skills
            ),
            default=0,
        )
        for item in skills:
            tests = item["tests"]
            test_label = (
                f"{tests['passed']}/{tests['total']}" if tests["total"] else "missing"
            )
            recent = item["last_direct_call"]
            recent = recent[:10] if recent != "never" else recent
            direct = item["direct_calls"]
            indirect = item.get("indirect_calls", 0)
            lines.append(
                f"{item['name']:<{name_width}}  {direct:>4}  {indirect:>4}  "
                f"{recent:<10}  {test_label:<7}  {_stacked_bar(direct, indirect, max_total)}"
            )
        lines.extend(
            (
                "",
                "Legend",
                f"{_DIRECT_MARK} direct = activation (main-session skill read)",
                (
                    f"{_INDIRECT_MARK} indirect = broad_scan (≥4 skills/session) "
                    "+ worker_read (subagent/sidechain)"
                ),
            )
        )

    suggestion_rows = list(suggestions or report.get("suggestions") or ())
    if suggestion_rows:
        lines.extend(("", *_render_suggestion_sections(suggestion_rows, skills)))

    lines.extend(("", "Limits"))
    lines.extend(f"- {item}" for item in report["limits"])
    return "\n".join(lines)


def _render_suggestion_sections(
    suggestions: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    *,
    max_each: int = 5,
) -> list[str]:
    """Render plain-language delete/downgrade blocks (no abstract 'lifecycle' label)."""
    by_name = {item["name"]: item for item in skills}
    deletes = [item for item in suggestions if item.get("action") == "delete_candidate"]
    downgrades = [item for item in suggestions if item.get("action") == "downgrade"]
    merges = [item for item in suggestions if item.get("action") == "merge"]
    projectize = [item for item in suggestions if item.get("action") == "projectize"]

    lines = ["Suggestions (read-only candidates; not applied)"]
    lines.extend(
        _section(
            "Delete candidates",
            "no usage + no tests + no owner evidence — review before removing",
            deletes[:max_each],
            by_name,
        )
    )
    lines.extend(
        _section(
            "Downgrade candidates",
            "mostly broad/worker reads; may be a part of another skill, not a standalone",
            downgrades[:max_each],
            by_name,
        )
    )
    if merges:
        lines.extend(
            _section(
                "Merge candidates",
                "overlap / co-use — optional second look",
                merges[:max_each],
                by_name,
            )
        )
    if projectize:
        lines.extend(
            _section(
                "Projectize candidates",
                "looks project-local — optional second look",
                projectize[:max_each],
                by_name,
            )
        )
    return lines


def _section(
    title: str,
    blurb: str,
    items: list[dict[str, Any]],
    by_name: dict[str, dict[str, Any]],
) -> list[str]:
    lines = [f"{title}  ({len(items)})", f"  {blurb}"]
    if not items:
        lines.append("  (none)")
        return lines
    for item in items:
        target = str(item.get("target") or "")
        skill = by_name.get(target)
        if skill is not None:
            stats = f"{skill['direct_calls']}d/{skill.get('indirect_calls', 0)}i"
        else:
            stats = "n/a"
        reason = str(item.get("reason") or "").strip()
        if len(reason) > 72:
            reason = reason[:69] + "..."
        lines.append(f"  - {target}  [{stats}]  {reason}")
    return lines


def _stacked_bar(direct: int, indirect: int, maximum: int, width: int = _BAR_WIDTH) -> str:
    total = direct + indirect
    if maximum <= 0 or total <= 0:
        return _EMPTY_MARK * width

    direct_width = round(direct / maximum * width) if direct else 0
    indirect_width = round(indirect / maximum * width) if indirect else 0
    if direct > 0 and direct_width == 0:
        direct_width = 1
    if indirect > 0 and indirect_width == 0:
        indirect_width = 1

    filled = direct_width + indirect_width
    if filled > width:
        overflow = filled - width
        # Prefer shrinking the larger segment.
        if indirect_width >= direct_width:
            indirect_width = max(1 if indirect else 0, indirect_width - overflow)
        else:
            direct_width = max(1 if direct else 0, direct_width - overflow)
        filled = direct_width + indirect_width
        if filled > width:
            direct_width = max(0, direct_width - (filled - width))
            filled = direct_width + indirect_width

    return (
        _DIRECT_MARK * direct_width
        + _INDIRECT_MARK * indirect_width
        + _EMPTY_MARK * max(0, width - filled)
    )


def _event(event: object) -> dict[str, str]:
    if hasattr(event, "to_dict"):
        event = event.to_dict()
    source = event if isinstance(event, dict) else {}
    return {
        "timestamp": str(source.get("timestamp", "")),
        "skill": str(source.get("skill", "")),
        "category": str(source.get("category", "unknown")),
        "harness": str(source.get("harness", "")),
    }


def _tests_by_skill(test_runs: tuple[dict[str, Any], ...]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0})
    for run in test_runs:
        if not isinstance(run, dict):
            continue
        skill = str(run.get("skill") or run.get("target") or "")
        if not skill:
            continue
        trials = run.get("trials") or run.get("results") or [run]
        if not isinstance(trials, list):
            trials = [run]
        for trial in trials:
            row = trial if isinstance(trial, dict) else {}
            status = str(row.get("status") or row.get("outcome_status") or "")
            result[skill]["total"] += 1
            result[skill]["passed"] += int(status in {"pass", "outcome_pass"})
    return dict(result)
