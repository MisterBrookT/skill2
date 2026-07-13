from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

SCHEMA_VERSION: Final = "1"


class Severity(StrEnum):
    ERROR = "ERROR"
    WARN = "WARN"
    ADVICE = "ADVICE"


@dataclass(frozen=True)
class ResourceLink:
    target: str
    kind: str
    exists: bool


@dataclass(frozen=True)
class ScriptRecord:
    path: str
    executable: bool


@dataclass(frozen=True)
class SkillSource:
    text: str
    body: str
    frontmatter: dict[str, Any] | None
    frontmatter_error: str | None
    links: tuple[ResourceLink, ...] = ()
    scripts: tuple[ScriptRecord, ...] = ()


@dataclass(frozen=True)
class SkillRecord:
    name: str
    path: str
    description: str
    body_tokens: int
    references: tuple[str, ...]
    scripts: tuple[str, ...]
    assets: tuple[str, ...]
    scope: str
    hash: str
    _source: SkillSource = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "body_tokens": self.body_tokens,
            "references": list(self.references),
            "scripts": list(self.scripts),
            "assets": list(self.assets),
            "scope": self.scope,
            "hash": self.hash,
        }


@dataclass(frozen=True)
class ScanResult:
    root: str
    skills: tuple[SkillRecord, ...]
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "root": self.root,
            "skills": [skill.to_dict() for skill in self.skills],
        }


@dataclass(frozen=True)
class Issue:
    severity: Severity
    path: str
    message: str
    rule_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity.value,
            "path": self.path,
            "message": self.message,
            "rule_id": self.rule_id,
        }


@dataclass(frozen=True)
class LintResult:
    root: str
    checked: int
    issues: tuple[Issue, ...]
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity is Severity.ERROR for issue in self.issues)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "root": self.root,
            "checked": self.checked,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class Case:
    id: str
    name: str
    prompt: str
    kind: str = "core_positive"
    expect_activation: str | None = None
    expect_not_activation: tuple[str, ...] = ()
    assertions: tuple[dict[str, Any], ...] = ()
    fixture: str | None = None
    repetitions: int = 1
    schema_version: str = field(default=SCHEMA_VERSION, init=False)


@dataclass(frozen=True)
class TrialResult:
    case_id: str
    trial: int
    mode: str
    status: str
    activation_status: str
    outcome_status: str
    activations: tuple[str, ...]
    activation_confidence: dict[str, str]
    exit_code: int
    duration_ms: int
    assertions: tuple[dict[str, Any], ...] = ()
    evidence: tuple[str, ...] = ()
    artifact_dir: str = ""
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "trial": self.trial,
            "mode": self.mode,
            "status": self.status,
            "activation_status": self.activation_status,
            "outcome_status": self.outcome_status,
            "activations": list(self.activations),
            "activation_confidence": self.activation_confidence,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "assertions": list(self.assertions),
            "evidence": list(self.evidence),
            "artifact_dir": self.artifact_dir,
        }


@dataclass(frozen=True)
class TestRun:
    run_id: str
    skill: str
    agent: str
    skill_hash: str
    cases_path: str
    trials: tuple[TrialResult, ...]
    complete: bool = True
    stopped_early: bool = False
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    @property
    def passed(self) -> bool:
        return self.complete and all(
            trial.status in {"pass", "baseline"} for trial in self.trials
        )

    def to_dict(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for trial in self.trials:
            counts[trial.status] = counts.get(trial.status, 0) + 1
        comparisons = _baseline_comparisons(self.trials)
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "skill": self.skill,
            "agent": self.agent,
            "skill_hash": self.skill_hash,
            "cases_path": self.cases_path,
            "passed": self.passed,
            "complete": self.complete,
            "stopped_early": self.stopped_early,
            "summary": counts,
            "baseline_comparison": comparisons,
            "trials": [trial.to_dict() for trial in self.trials],
        }


def _baseline_comparisons(trials: tuple[TrialResult, ...]) -> list[dict[str, Any]]:
    indexed = {(trial.case_id, trial.trial, trial.mode): trial for trial in trials}
    comparisons: list[dict[str, Any]] = []
    for trial in trials:
        if trial.mode != "with_skill":
            continue
        baseline = indexed.get((trial.case_id, trial.trial, "baseline"))
        if baseline is None:
            continue
        comparisons.append(
            {
                "case_id": trial.case_id,
                "trial": trial.trial,
                "with_skill_outcome": trial.outcome_status,
                "baseline_outcome": baseline.outcome_status,
                "deterministic_uplift": trial.outcome_status == "outcome_pass"
                and baseline.outcome_status == "outcome_fail",
            }
        )
    return comparisons


@dataclass(frozen=True)
class ActivationEvent:
    timestamp: str
    harness: str
    session: str
    skill: str
    source: str
    confidence: float
    schema_version: str = field(default=SCHEMA_VERSION, init=False)


@dataclass(frozen=True)
class Suggestion:
    action: str
    target: str
    reason: str
    evidence: tuple[str, ...]
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
