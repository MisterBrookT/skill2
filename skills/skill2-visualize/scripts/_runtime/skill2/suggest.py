from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from .models import SCHEMA_VERSION, ScanResult, SkillRecord, Suggestion
from .usage import UsageResult

_WORDS = re.compile(r"[a-z0-9]+")
_NON_DIRECT_CATEGORIES = {"broad_scan", "worker_read"}


@dataclass(frozen=True)
class SuggestionResult:
    suggestions: tuple[Suggestion, ...]
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "suggestions": [
                {
                    "action": suggestion.action,
                    "target": suggestion.target,
                    "reason": suggestion.reason,
                    "evidence": list(suggestion.evidence),
                }
                for suggestion in self.suggestions
            ],
        }


def build_suggestions(
    scan: ScanResult,
    usage: UsageResult,
    test_runs: tuple[dict[str, Any], ...] = (),
) -> SuggestionResult:
    """Return conservative, read-only skill maintenance suggestions."""
    events = tuple(_event(event) for event in usage.events)
    tests = _test_summary(test_runs)
    by_skill: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_session: dict[str, set[str]] = defaultdict(set)
    for event in events:
        by_skill[event["skill"]].append(event)
        if (
            event["category"] == "activation"
            and event["session"]
            and event["skill"]
        ):
            by_session[event["session"]].add(event["skill"])

    suggestions: list[Suggestion] = []
    merge_members: set[str] = set()
    for left, right, sessions in _merge_candidates(scan.skills, by_session):
        merge_members.update((left.name, right.name))
        suggestions.append(
            Suggestion(
                action="merge",
                target=f"{left.name} + {right.name}",
                reason=(
                    "Repeated same-session use and overlapping trigger language "
                    "suggest one boundary."
                ),
                evidence=(
                    f"co-occurred in {len(sessions)} sessions: {', '.join(sessions)}",
                    f"shared trigger terms: {', '.join(_overlap(left, right))}",
                ),
            )
        )

    for skill in sorted(scan.skills, key=lambda item: item.name):
        skill_events = by_skill.get(skill.name, [])
        direct = [event for event in skill_events if event["category"] == "activation"]
        non_direct = [
            event for event in skill_events if event["category"] in _NON_DIRECT_CATEGORIES
        ]
        test = tests[skill.name]
        if _has_project_evidence(skill):
            suggestions.append(
                Suggestion(
                    action="projectize",
                    target=skill.name,
                    reason="The inventory gives explicit project-local ownership evidence.",
                    evidence=_project_evidence(skill),
                )
            )
        elif skill.name in merge_members:
            continue
        elif test["passed"] > 0 or len(direct) >= 3:
            suggestions.append(
                Suggestion(
                    action="keep",
                    target=skill.name,
                    reason=(
                        "Direct activation or isolated test evidence supports retaining this skill."
                    ),
                    evidence=_keep_evidence(direct, test),
                )
            )
        elif len(direct) <= 1 and len(non_direct) >= 2 and len(non_direct) > len(direct):
            suggestions.append(
                Suggestion(
                    action="downgrade",
                    target=skill.name,
                    reason=(
                        "Observed use is low-confidence broad or worker reading rather than direct "
                        "activation."
                    ),
                    evidence=tuple(
                        [
                            f"direct activations: {len(direct)}",
                            f"broad/worker reads: {len(non_direct)}",
                        ]
                        + _event_evidence(non_direct)
                    ),
                )
            )
        elif not skill_events and test["total"] == 0 and not _has_owner_evidence(skill):
            suggestions.append(
                Suggestion(
                    action="delete_candidate",
                    target=skill.name,
                    reason=(
                        "No usage signal, test evidence, or ownership evidence was found; "
                        "manual review required."
                    ),
                    evidence=(
                        "direct activations: 0",
                        "all observed usage events: 0",
                        "test runs: 0",
                        "owner evidence: none",
                    ),
                )
            )

    return SuggestionResult(
        suggestions=tuple(sorted(suggestions, key=lambda item: (item.action, item.target)))
    )


def _event(event: object) -> dict[str, str]:
    if hasattr(event, "to_dict"):
        event = event.to_dict()
    if not isinstance(event, dict):
        return {"timestamp": "", "session": "", "skill": "", "category": "unknown"}
    return {
        "timestamp": str(event.get("timestamp", "")),
        "session": str(event.get("session", "")),
        "skill": str(event.get("skill", "")),
        "category": str(event.get("category", "unknown")),
    }


def _merge_candidates(
    skills: tuple[SkillRecord, ...], by_session: dict[str, set[str]]
) -> tuple[tuple[SkillRecord, SkillRecord, tuple[str, ...]], ...]:
    by_name = {skill.name: skill for skill in skills}
    sessions_by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    sessions_by_skill: Counter[str] = Counter()
    for session, names in by_session.items():
        known = sorted(name for name in names if name in by_name)
        for name in known:
            sessions_by_skill[name] += 1
        for pair in combinations(known, 2):
            sessions_by_pair[pair].append(session)

    candidates: list[tuple[SkillRecord, SkillRecord, tuple[str, ...]]] = []
    for (left_name, right_name), sessions in sessions_by_pair.items():
        overlap = _overlap(by_name[left_name], by_name[right_name])
        support = len(sessions)
        denominator = min(sessions_by_skill[left_name], sessions_by_skill[right_name])
        if support >= 2 and denominator and support / denominator >= 0.75 and overlap:
            candidates.append((by_name[left_name], by_name[right_name], tuple(sorted(sessions))))
    return tuple(sorted(candidates, key=lambda item: (item[0].name, item[1].name)))


def _overlap(left: SkillRecord, right: SkillRecord) -> tuple[str, ...]:
    left_words = _terms(f"{left.name} {left.description}")
    right_words = _terms(f"{right.name} {right.description}")
    return tuple(sorted(left_words & right_words))


def _terms(value: str) -> set[str]:
    return {word for word in _WORDS.findall(value.lower()) if len(word) >= 4}


def _test_summary(test_runs: tuple[dict[str, Any], ...]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0})
    for run in test_runs:
        if not isinstance(run, dict):
            continue
        skill = str(run.get("skill") or run.get("target") or "")
        if not skill:
            continue
        trials = run.get("trials") or run.get("results")
        if isinstance(trials, list):
            total = len(trials)
            passed = sum(
                1
                for trial in trials
                if isinstance(trial, dict)
                and str(trial.get("status") or trial.get("outcome_status") or "")
                in {"pass", "outcome_pass"}
            )
        else:
            total = 1
            passed = int(run.get("passed") is True or run.get("status") == "pass")
        summary[skill]["total"] += total
        summary[skill]["passed"] += passed
    return summary


def _has_project_evidence(skill: SkillRecord) -> bool:
    return _declared_scope(skill) == "project"


def _has_owner_evidence(skill: SkillRecord) -> bool:
    return _has_project_evidence(skill)


def _project_evidence(skill: SkillRecord) -> tuple[str, ...]:
    return ("frontmatter metadata.skill2.scope: project",)


def _declared_scope(skill: SkillRecord) -> str:
    frontmatter = skill._source.frontmatter or {}
    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    skill2 = metadata.get("skill2")
    if not isinstance(skill2, dict):
        return ""
    return str(skill2.get("scope", "")).lower()


def _keep_evidence(direct: list[dict[str, str]], test: dict[str, int]) -> tuple[str, ...]:
    evidence = []
    if direct:
        evidence.append(f"direct activations: {len(direct)}")
        evidence.extend(_event_evidence(direct))
    if test["passed"]:
        evidence.append(f"passing test trials: {test['passed']} of {test['total']}")
    return tuple(evidence)


def _event_evidence(events: list[dict[str, str]]) -> list[str]:
    return [
        "event: "
        f"session={event['session']} timestamp={event['timestamp']} "
        f"category={event['category']}"
        for event in events
    ]
