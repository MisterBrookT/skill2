from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import SCHEMA_VERSION, Case


@dataclass(frozen=True)
class CaseSuite:
    skill: str
    agent: str
    cases: tuple[Case, ...]
    path: str
    schema_version: str = SCHEMA_VERSION


def load_case_suite(path: Path) -> CaseSuite:
    resolved = path.expanduser().resolve()
    try:
        payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot load cases: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("case file must be a YAML mapping")

    skill = _required_string(payload, "skill")
    agent = str(payload.get("agent") or "codex")
    if agent not in {"codex", "claude"}:
        raise ValueError("case agent must be `codex` or `claude`")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("case file needs a non-empty `cases` list")

    defaults = payload.get("defaults") if isinstance(payload.get("defaults"), dict) else {}
    default_repetitions = _positive_int(defaults.get("repetitions", 1), "defaults.repetitions")
    cases = tuple(
        _parse_case(item, index, default_repetitions) for index, item in enumerate(raw_cases, 1)
    )
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("case ids must be unique")
    return CaseSuite(skill=skill, agent=agent, cases=cases, path=str(resolved))


def _parse_case(raw: Any, index: int, default_repetitions: int) -> Case:
    if not isinstance(raw, dict):
        raise ValueError(f"case {index} must be a mapping")
    name = str(raw.get("name") or raw.get("id") or f"case-{index}")
    case_id = str(raw.get("id") or _slug(name) or f"case-{index}")
    prompt = _required_string(raw, "prompt", prefix=f"case {case_id}: ")
    expect_activation = raw.get("expect_activation")
    if expect_activation is not None and not isinstance(expect_activation, str):
        raise ValueError(f"case {case_id}: expect_activation must be a string")
    expect_not = raw.get("expect_not_activation") or []
    if not isinstance(expect_not, list) or not all(isinstance(value, str) for value in expect_not):
        raise ValueError(f"case {case_id}: expect_not_activation must be a string list")
    assertions = raw.get("assertions") or []
    if not isinstance(assertions, list) or not all(isinstance(value, dict) for value in assertions):
        raise ValueError(f"case {case_id}: assertions must be a mapping list")
    fixture = raw.get("fixture")
    if fixture is not None and not isinstance(fixture, str):
        raise ValueError(f"case {case_id}: fixture must be a string")
    repetitions = _positive_int(raw.get("repetitions", default_repetitions), "repetitions")
    return Case(
        id=case_id,
        name=name,
        kind=str(raw.get("kind") or _infer_kind(expect_activation, expect_not)),
        prompt=prompt,
        expect_activation=expect_activation,
        expect_not_activation=tuple(expect_not),
        assertions=tuple(assertions),
        fixture=fixture,
        repetitions=repetitions,
    )


def _required_string(payload: dict[str, Any], key: str, *, prefix: str = "") -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{prefix}missing `{key}`")
    return value


def _positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:64]


def _infer_kind(expect_activation: str | None, expect_not: list[str]) -> str:
    if expect_activation:
        return "core_positive"
    if expect_not:
        return "negative"
    return "outcome"
