from __future__ import annotations

import re
from pathlib import Path

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def scaffold_skill(name: str, output_dir: Path, description: str | None = None) -> list[str]:
    if not _NAME_RE.match(name):
        raise SystemExit(f"invalid skill name: {name}")

    skill_dir = output_dir / name
    skill_file = skill_dir / "SKILL.md"
    if skill_file.exists():
        raise SystemExit(f"skill already exists: {skill_file}")

    skill_dir.mkdir(parents=True, exist_ok=False)
    text = _skill_template(name, description or f"Use when the user needs {name}.")
    skill_file.write_text(text, encoding="utf-8")
    return [str(skill_file)]


def _skill_template(name: str, description: str) -> str:
    return f"""---
name: {name}
description: "{description}"
---

# {name}

原则：在触发场景下用最短规则做对判断；不写通用流水账。

## Scope

- 只覆盖本 skill 的独立触发；相邻职责另开 skill 或放 reference。
- 重细节进 `references/`；确定性动作进 `scripts/` / validator。

## 决策

| 情况 | 动作 |
| --- | --- |
| 缺关键事实 | 先问再写 |
| 可脚本化 | 写 script/validator，不写长 checklist |
| 一次性回答 | 不做 skill |

## 质量门

- `description` 只写触发，不写流程。
- 正文短；无 secrets；无无关绝对路径。
"""
