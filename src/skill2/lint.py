from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from skills_ref import validate as validate_agent_skill

from .models import Issue, LintResult, ScanResult, Severity, SkillRecord
from .scan import scan_path

_LOCAL_PATH_RE = re.compile(r"/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/")
_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9_]{8,}|(?:api[_-]?key|password|secret|token)\s*[:=])",
    re.I,
)
_SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARN: 1, Severity.ADVICE: 2}


def lint_scan(scan: ScanResult) -> LintResult:
    issues: list[Issue] = []
    for skill in scan.skills:
        issues.extend(_lint_skill(skill))

    duplicates = {
        name for name, count in Counter(skill.name for skill in scan.skills).items() if count > 1
    }
    for skill in scan.skills:
        if skill.name in duplicates:
            issues.append(
                Issue(
                    Severity.ERROR,
                    skill.path,
                    f"duplicate skill name: {skill.name}",
                    "S2F005",
                )
            )

    if not scan.skills:
        issues.append(Issue(Severity.ERROR, scan.root, "no SKILL.md found", "S2F000"))

    ordered = tuple(
        sorted(
            issues,
            key=lambda issue: (
                issue.path,
                _SEVERITY_ORDER[issue.severity],
                issue.rule_id,
                issue.message,
            ),
        )
    )
    return LintResult(root=scan.root, checked=len(scan.skills), issues=ordered)


def lint_path(path: Path) -> LintResult:
    return lint_scan(scan_path(path))


def _lint_skill(skill: SkillRecord) -> list[Issue]:
    source = skill._source
    path = skill.path
    issues: list[Issue] = []

    if source.frontmatter_error:
        issues.append(Issue(Severity.ERROR, path, source.frontmatter_error, "S2F001"))
        return issues

    for message in validate_agent_skill(Path(path).parent):
        issues.append(Issue(Severity.ERROR, path, message, "S2A001"))

    description = (source.frontmatter or {}).get("description")
    if isinstance(description, str) and len(description) > 140:
        issues.append(Issue(Severity.WARN, path, "description too long", "S2Q001"))

    if len(source.body.strip()) < 40:
        issues.append(Issue(Severity.WARN, path, "body too short", "S2Q002"))
    if skill.body_tokens > 2_000:
        issues.append(
            Issue(
                Severity.ADVICE,
                path,
                "large body; consider moving detail to references",
                "S2Q003",
            )
        )
    if _LOCAL_PATH_RE.search(source.body):
        issues.append(Issue(Severity.WARN, path, "contains machine-local absolute path", "S2P001"))
    if _SECRET_RE.search(source.text):
        issues.append(Issue(Severity.ERROR, path, "possible secret or credential text", "S2S001"))

    for script in source.scripts:
        if not script.executable:
            issues.append(
                Issue(
                    Severity.WARN,
                    str(Path(path).parent / script.path),
                    "script is not executable",
                    "S2X001",
                )
            )

    for link in source.links:
        if link.exists:
            continue
        label = {"assets": "asset", "scripts": "script"}.get(link.kind, "reference")
        issues.append(
            Issue(
                Severity.ERROR,
                path,
                f"missing {label}: {link.target}",
                "S2L001",
            )
        )

    return issues


__all__ = [
    "Issue",
    "LintResult",
    "Severity",
    "lint_path",
    "lint_scan",
]
