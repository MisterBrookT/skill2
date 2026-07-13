from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml
from markdown_it import MarkdownIt

from .models import ResourceLink, ScanResult, ScriptRecord, SkillRecord, SkillSource

_MARKDOWN = MarkdownIt("commonmark")
_TOKEN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]")
_EXECUTABLE_SUFFIXES = {".bash", ".js", ".pl", ".py", ".rb", ".sh", ".ts", ".zsh"}
_IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}


def scan_path(path: Path) -> ScanResult:
    root = path.expanduser().resolve()
    skill_files = _find_skill_files(root)
    skills = tuple(_scan_skill(skill_file) for skill_file in skill_files)
    return ScanResult(root=str(root), skills=skills)


def _find_skill_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.name == "SKILL.md" else []
    if not path.is_dir():
        return []
    direct = path / "SKILL.md"
    if direct.is_file():
        return [direct.resolve()]

    found: list[Path] = []
    for current, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = sorted(
            directory
            for directory in dirs
            if directory not in _IGNORED_DIRS and not (Path(current) / directory).is_symlink()
        )
        if "SKILL.md" in files:
            found.append((Path(current) / "SKILL.md").resolve())
    return sorted(set(found), key=lambda item: item.as_posix())


def _scan_skill(skill_file: Path) -> SkillRecord:
    raw = skill_file.read_bytes()
    text = raw.decode("utf-8")
    frontmatter, body, error = _parse_frontmatter(text)
    links = _markdown_links(body, skill_file.parent)
    inventories = {
        kind: _resource_files(skill_file.parent, kind)
        for kind in ("references", "scripts", "assets")
    }

    for link in links:
        if link.kind in inventories:
            inventories[link.kind].add(link.target)

    name = _string_value(frontmatter, "name") or skill_file.parent.name
    description = _string_value(frontmatter, "description")
    scripts = tuple(sorted(inventories["scripts"]))
    script_records = tuple(
        ScriptRecord(
            path=script,
            executable=_is_executable(skill_file.parent / script),
        )
        for script in scripts
        if (skill_file.parent / script).is_file()
    )
    return SkillRecord(
        name=name,
        path=str(skill_file),
        description=description,
        body_tokens=len(_TOKEN_RE.findall(body)),
        references=tuple(sorted(inventories["references"])),
        scripts=scripts,
        assets=tuple(sorted(inventories["assets"])),
        scope=_scope(skill_file, frontmatter),
        hash=hashlib.sha256(raw).hexdigest(),
        _source=SkillSource(
            text=text,
            body=body,
            frontmatter=frontmatter,
            frontmatter_error=error,
            links=tuple(links),
            scripts=script_records,
        ),
    )


def _parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str, str | None]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].removeprefix("\ufeff").strip() != "---":
        return None, text, "missing frontmatter"

    end = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        return None, text, "unterminated frontmatter"

    raw = "".join(lines[1:end])
    body = "".join(lines[end + 1 :])
    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        return None, body, f"invalid YAML frontmatter: {problem}"
    if loaded is None:
        return {}, body, None
    if not isinstance(loaded, dict):
        return None, body, "frontmatter must be a YAML mapping"
    return loaded, body, None


def _markdown_links(body: str, skill_dir: Path) -> list[ResourceLink]:
    links: set[tuple[str, str, bool]] = set()
    for token in _walk_tokens(_MARKDOWN.parse(body)):
        attribute = (
            "src" if token.type == "image" else "href" if token.type == "link_open" else None
        )
        if attribute is None:
            continue
        raw_target = token.attrGet(attribute)
        target = _normalize_local_target(raw_target or "", skill_dir)
        if target is None:
            continue
        kind = _resource_kind(target, image=token.type == "image")
        links.add((target, kind, (skill_dir / target).exists()))
    return [ResourceLink(*values) for values in sorted(links)]


def _walk_tokens(tokens: list[Any]) -> list[Any]:
    flattened: list[Any] = []
    for token in tokens:
        flattened.append(token)
        if token.children:
            flattened.extend(_walk_tokens(token.children))
    return flattened


def _normalize_local_target(raw_target: str, skill_dir: Path) -> str | None:
    target = raw_target.strip().strip("<>")
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
        return None
    path = unquote(parsed.path).replace("\\", "/")
    resolved = (skill_dir / path).resolve()
    try:
        return resolved.relative_to(skill_dir.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _resource_kind(path: str, *, image: bool) -> str:
    first = Path(path).parts[0] if Path(path).parts else ""
    if first == "scripts":
        return "scripts"
    if image or first == "assets":
        return "assets"
    return "references"


def _resource_files(skill_dir: Path, kind: str) -> set[str]:
    resource_dir = skill_dir / kind
    if not resource_dir.is_dir() or resource_dir.is_symlink():
        return set()
    return {
        path.relative_to(skill_dir).as_posix()
        for path in resource_dir.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def _string_value(frontmatter: dict[str, Any] | None, key: str) -> str:
    if not frontmatter:
        return ""
    value = frontmatter.get(key)
    return value if isinstance(value, str) else ""


def _scope(skill_file: Path, frontmatter: dict[str, Any] | None) -> str:
    explicit = _string_value(frontmatter, "scope")
    if explicit:
        return explicit
    home = Path.home().resolve()
    global_roots = (
        home / ".agents" / "skills",
        home / ".codex" / "skills",
        home / ".claude" / "skills",
    )
    if any(_is_relative_to(skill_file, root) for root in global_roots):
        return "global"
    return "project"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_executable(path: Path) -> bool:
    if path.suffix.lower() not in _EXECUTABLE_SUFFIXES:
        return True
    return bool(path.stat().st_mode & 0o111)
