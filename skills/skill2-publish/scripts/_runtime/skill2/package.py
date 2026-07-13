from __future__ import annotations

import json
import os
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .lint import lint_path
from .models import SCHEMA_VERSION, Issue, Severity

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_SECRET_RE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,}|"
    r"AKIA[0-9A-Z]{16}|(?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?"
    r"(?!\$\{|\$\()[^\s'\"]{6,})",
    re.IGNORECASE,
)
_LOCAL_ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s'\"])(?:/Users/|/home/|file:///)")
_DESTRUCTIVE_COMMAND_RE = re.compile(
    r"(?:rm\s+-[A-Za-z]*r[A-Za-z]*f[A-Za-z]*\s+/\s*$|mkfs(?:\.[A-Za-z0-9]+)?\b|"
    r"dd\s+[^\n]*\bof=/dev/|:\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*}\s*;\s*:)",
    re.MULTILINE,
)
_PIPE_SHELL_RE = re.compile(r"\b(?:curl|wget)\b[^\n]*\|\s*(?:ba)?sh\b", re.IGNORECASE)
_INSTALL_COMMAND_RE = re.compile(
    r"^\s*(?:curl\b[^\n]*\|\s*(?:ba)?sh\b|wget\b[^\n]*\|\s*(?:ba)?sh\b|"
    r"(?:uv\s+tool|pip(?:x)?|npm|brew)\s+install\b|(?:\.?/)?install\.sh\b|git\s+clone\b).*$",
    re.IGNORECASE | re.MULTILINE,
)
_IGNORED_DIRS = {
    ".skill2",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "src",
    "tests",
}
_REQUIRED_FILES = ("README.md", "LICENSE", "CHANGELOG.md", "install.sh")


@dataclass(frozen=True)
class PackageResult:
    root: str
    issues: tuple[Issue, ...]
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity is Severity.ERROR for issue in self.issues)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "root": self.root,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def package_check(path: Path) -> PackageResult:
    root = path.expanduser().resolve()
    issues: list[Issue] = []
    if not root.is_dir():
        return _result(
            root, [Issue(Severity.ERROR, str(root), "repository directory is missing", "P2R001")]
        )

    skills_dir = root / "skills"
    if not skills_dir.is_dir() or skills_dir.is_symlink():
        issues.append(Issue(Severity.ERROR, str(skills_dir), "missing skills directory", "P2R001"))
    else:
        issues.extend(lint_path(skills_dir).issues)

    for relative in _REQUIRED_FILES:
        required = root / relative
        if not required.is_file() or required.is_symlink():
            issues.append(
                Issue(Severity.ERROR, str(required), f"missing required file: {relative}", "P2R002")
            )

    issues.extend(_symlink_issues(root))
    issues.extend(_bash_issues(root))
    manifest_issues, _ = _manifest_issues(root)
    issues.extend(manifest_issues)
    issues.extend(_claude_marketplace_issues(root))
    issues.extend(_content_issues(root))
    return _result(root, issues)


def publish_preflight(path: Path) -> PackageResult:
    result = package_check(path)
    root = Path(result.root)
    issues = list(result.issues)
    issues.extend(_bilingual_readme_issues(root))
    issues.extend(_brand_graphic_issues(root))
    issues.extend(_install_command_issues(root))
    issues.extend(_version_consistency_issues(root))
    issues.extend(_git_status_issues(root))
    return _result(root, issues)


def scaffold_skill_repo(name: str, output_dir: Path) -> list[str]:
    if not _NAME_RE.fullmatch(name):
        raise ValueError(f"invalid skill repo name: {name}")

    root = output_dir.expanduser() / name
    if root.exists():
        raise FileExistsError(f"output already exists: {root}")

    skill_dir = root / "skills" / name
    brand_path = root / "assets" / f"{name}-icon.svg"
    files = {
        root / "README.md": _english_readme(name),
        root / "README.zh.md": _chinese_readme(name),
        root / "LICENSE": "MIT License\n\nCopyright (c) 2026\n",
        root / "CHANGELOG.md": "# Changelog\n\n## 0.1.0\n\n- Initial release.\n",
        root / "install.sh": _installer(),
        root / "pyproject.toml": _pyproject(name),
        root / ".codex-plugin" / "plugin.json": json.dumps(
            {
                "name": name,
                "version": "0.1.0",
                "description": f"{name} skill repository.",
                "skills": "skills",
                "license": "MIT",
            },
            indent=2,
        )
        + "\n",
        root / ".claude-plugin" / "plugin.json": json.dumps(
            {
                "name": name,
                "version": "0.1.0",
                "description": f"{name} skill repository.",
                "license": "MIT",
            },
            indent=2,
        )
        + "\n",
        root / ".claude-plugin" / "marketplace.json": json.dumps(
            {
                "name": f"{name}-marketplace",
                "description": f"{name} skill marketplace.",
                "owner": {"name": "TODO"},
                "plugins": [
                    {
                        "name": name,
                        "description": f"{name} skill repository.",
                        "version": "0.1.0",
                        "source": "./",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        skill_dir / "SKILL.md": _skill_file(name),
        brand_path: _brand_svg(name),
    }
    for target, content in files.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    (root / "install.sh").chmod(0o755)
    return [str(target) for target in sorted(files)]


def _result(root: Path, issues: list[Issue]) -> PackageResult:
    order = {Severity.ERROR: 0, Severity.WARN: 1, Severity.ADVICE: 2}
    unique = {(issue.severity, issue.path, issue.message, issue.rule_id): issue for issue in issues}
    ordered = tuple(
        sorted(
            unique.values(),
            key=lambda issue: (issue.path, order[issue.severity], issue.rule_id, issue.message),
        )
    )
    return PackageResult(root=str(root), issues=ordered)


def _symlink_issues(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirs[:] = [directory for directory in dirs if directory not in _IGNORED_DIRS]
        for entry in [*dirs, *files]:
            candidate = current_path / entry
            if candidate.is_symlink():
                issues.append(
                    Issue(Severity.ERROR, str(candidate), "symlinks are not packageable", "P2R003")
                )
    return issues


def _bash_issues(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for candidate in _iter_files(root):
        if candidate.name != "install.sh" and candidate.suffix not in {".bash", ".sh"}:
            continue
        completed = subprocess.run(
            ["bash", "-n", str(candidate)], text=True, capture_output=True, check=False
        )
        if completed.returncode:
            detail = (completed.stderr or completed.stdout).strip().splitlines()
            message = detail[0] if detail else "bash syntax check failed"
            issues.append(Issue(Severity.ERROR, str(candidate), message, "P2B001"))
    return issues


def _manifest_issues(root: Path) -> tuple[list[Issue], list[tuple[Path, dict[str, object]]]]:
    candidates = [
        root / "manifest.json",
        root / ".codex-plugin" / "plugin.json",
        root / ".claude-plugin" / "plugin.json",
    ]
    manifests: list[tuple[Path, dict[str, object]]] = []
    issues: list[Issue] = []
    for candidate in candidates:
        if not candidate.exists():
            continue
        if not candidate.is_file() or candidate.is_symlink():
            issues.append(
                Issue(
                    Severity.ERROR, str(candidate), "manifest must be a regular JSON file", "P2M001"
                )
            )
            continue
        try:
            loaded = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            issues.append(
                Issue(Severity.ERROR, str(candidate), f"invalid JSON manifest: {exc}", "P2M002")
            )
            continue
        if not isinstance(loaded, dict):
            issues.append(
                Issue(Severity.ERROR, str(candidate), "manifest must be a JSON object", "P2M002")
            )
            continue
        manifests.append((candidate, loaded))

    if not manifests:
        issues.append(
            Issue(Severity.ERROR, str(root), "no supported JSON manifest found", "P2M001")
        )
        return issues, manifests

    has_skills_path = False
    for candidate, manifest in manifests:
        require_version = candidate.name == "manifest.json" or candidate.parts[-2] in {
            ".codex-plugin",
            ".claude-plugin",
        }
        version = manifest.get("version")
        if require_version and not isinstance(version, str):
            issues.append(
                Issue(Severity.ERROR, str(candidate), "manifest is missing version", "P2M003")
            )
        elif version is not None and (
            not isinstance(version, str) or not _VERSION_RE.fullmatch(version)
        ):
            issues.append(
                Issue(Severity.ERROR, str(candidate), "manifest version must use semver", "P2M003")
            )

        skills = manifest.get("skills")
        if skills is None:
            continue
        has_skills_path = True
        if not isinstance(skills, str) or not skills or Path(skills).is_absolute():
            issues.append(
                Issue(
                    Severity.ERROR,
                    str(candidate),
                    "manifest skills must be a relative directory",
                    "P2M004",
                )
            )
            continue
        target = (root / skills).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            issues.append(
                Issue(
                    Severity.ERROR,
                    str(candidate),
                    "manifest skills path escapes repository",
                    "P2M004",
                )
            )
            continue
        if not target.is_dir() or target.is_symlink():
            issues.append(
                Issue(
                    Severity.ERROR, str(candidate), "manifest skills directory is missing", "P2M004"
                )
            )
    if not has_skills_path:
        issues.append(
            Issue(Severity.ERROR, str(root), "no manifest declares a skills path", "P2M004")
        )
    return issues, manifests


def _claude_marketplace_issues(root: Path) -> list[Issue]:
    marketplace_path = root / ".claude-plugin" / "marketplace.json"
    plugin_path = root / ".claude-plugin" / "plugin.json"
    if not marketplace_path.exists():
        return []
    try:
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [
            Issue(
                Severity.ERROR,
                str(marketplace_path),
                f"invalid Claude marketplace JSON: {exc}",
                "P2M005",
            )
        ]
    if not isinstance(marketplace, dict):
        return [
            Issue(
                Severity.ERROR,
                str(marketplace_path),
                "Claude marketplace must be a JSON object",
                "P2M005",
            )
        ]
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        return [
            Issue(
                Severity.ERROR,
                str(marketplace_path),
                "Claude marketplace needs a non-empty plugins list",
                "P2M005",
            )
        ]
    try:
        plugin_manifest = json.loads(plugin_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(plugin_manifest, dict):
        return []
    name = plugin_manifest.get("name")
    version = plugin_manifest.get("version")
    matches = [item for item in plugins if isinstance(item, dict) and item.get("name") == name]
    if len(matches) != 1:
        return [
            Issue(
                Severity.ERROR,
                str(marketplace_path),
                "Claude marketplace must contain exactly one entry for its plugin manifest",
                "P2M005",
            )
        ]
    entry = matches[0]
    if entry.get("source") != "./" or entry.get("version") != version:
        return [
            Issue(
                Severity.ERROR,
                str(marketplace_path),
                "Claude marketplace plugin source or version does not match plugin manifest",
                "P2M005",
            )
        ]
    return []


def _content_issues(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for candidate in _iter_files(root):
        text = _read_text(candidate)
        if text is None:
            continue
        if _SECRET_RE.search(text):
            issues.append(
                Issue(
                    Severity.ERROR, str(candidate), "possible secret or credential text", "P2S001"
                )
            )
        if _LOCAL_ABSOLUTE_PATH_RE.search(text):
            issues.append(
                Issue(
                    Severity.WARN, str(candidate), "contains machine-local absolute path", "P2S002"
                )
            )
        if _DESTRUCTIVE_COMMAND_RE.search(text):
            issues.append(
                Issue(Severity.ERROR, str(candidate), "contains destructive command", "P2S003")
            )
        elif _PIPE_SHELL_RE.search(text):
            issues.append(
                Issue(Severity.WARN, str(candidate), "contains pipe-to-shell command", "P2S004")
            )
    return issues


def _bilingual_readme_issues(root: Path) -> list[Issue]:
    english = root / "README.md"
    chinese = root / "README.zh.md"
    if not english.is_file() or not chinese.is_file():
        return [
            Issue(Severity.ERROR, str(root), "README.md and README.zh.md are required", "P2P001")
        ]
    english_text = _read_text(english) or ""
    chinese_text = _read_text(chinese) or ""
    issues: list[Issue] = []
    if not re.search(r"[A-Za-z]", english_text):
        issues.append(
            Issue(Severity.ERROR, str(english), "README.md must include English content", "P2P001")
        )
    if not re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", chinese_text):
        issues.append(
            Issue(
                Severity.ERROR, str(chinese), "README.zh.md must include Chinese content", "P2P001"
            )
        )
    return issues


def _brand_graphic_issues(root: Path) -> list[Issue]:
    readme = root / "README.md"
    text = _read_text(readme) or ""
    targets = re.findall(
        r"!\[[^]]*]\(([^)\s]+)\)|<img[^>]+src=[\"']([^\"']+)[\"']", text, re.IGNORECASE
    )
    for markdown_target, html_target in targets:
        target = markdown_target or html_target
        if re.match(r"https?://", target):
            continue
        candidate = (root / target).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file() and candidate.suffix.lower() in {
            ".gif",
            ".jpeg",
            ".jpg",
            ".png",
            ".svg",
            ".webp",
        }:
            return []
    return [
        Issue(
            Severity.ERROR, str(readme), "README.md must reference a local brand graphic", "P2P002"
        )
    ]


def _install_command_issues(root: Path) -> list[Issue]:
    commands: set[str] = set()
    for relative in ("README.md", "README.zh.md"):
        text = _read_text(root / relative) or ""
        commands.update(" ".join(match.split()) for match in _INSTALL_COMMAND_RE.findall(text))
    if len(commands) == 1:
        return []
    message = "README files must show one primary install command"
    return [Issue(Severity.ERROR, str(root / "README.md"), message, "P2P003")]


def _version_consistency_issues(root: Path) -> list[Issue]:
    versions: dict[str, str] = {}
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            return [
                Issue(Severity.ERROR, str(pyproject), f"invalid pyproject version: {exc}", "P2P004")
            ]
        version = project.get("version") if isinstance(project, dict) else None
        if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
            return [
                Issue(
                    Severity.ERROR,
                    str(pyproject),
                    "pyproject must declare a semver version",
                    "P2P004",
                )
            ]
        versions[str(pyproject)] = version
    _, manifests = _manifest_issues(root)
    for candidate, manifest in manifests:
        version = manifest.get("version")
        if isinstance(version, str):
            versions[str(candidate)] = version
    if len(set(versions.values())) > 1:
        return [
            Issue(Severity.ERROR, str(root), "project and manifest versions must match", "P2P004")
        ]
    return []


def _git_status_issues(root: Path) -> list[Issue]:
    completed = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        return [
            Issue(
                Severity.ERROR,
                str(root),
                "git status failed; repository must be initialized",
                "P2P005",
            )
        ]
    if completed.stdout.strip():
        return [Issue(Severity.ERROR, str(root), "git worktree is not clean", "P2P005")]
    return []


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(directory for directory in dirs if directory not in _IGNORED_DIRS)
        files.extend(Path(current) / name for name in sorted(names))
    return files


def _read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > 1_000_000 or b"\0" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _english_readme(name: str) -> str:
    return (
        f'<img src="assets/{name}-icon.svg" width="72" alt="{name} icon">\n\n'
        f"# {name}\n\n"
        "A reusable agent skill repository.\n\n"
        "## Install\n\n```bash\n./install.sh\n```\n"
    )


def _chinese_readme(name: str) -> str:
    return (
        f'<img src="assets/{name}-icon.svg" width="72" alt="{name} 图标">\n\n'
        f"# {name}\n\n"
        "可复用的 agent skill 仓库。\n\n"
        "## 安装\n\n```bash\n./install.sh\n```\n"
    )


def _installer() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:-all}"
case "$target" in
  all) destinations=("$HOME/.agents/skills" "$HOME/.claude/skills") ;;
  codex) destinations=("$HOME/.agents/skills") ;;
  claude) destinations=("$HOME/.claude/skills") ;;
  *) printf 'usage: ./install.sh [all|codex|claude]\\n' >&2; exit 2 ;;
esac
for destination in "${destinations[@]}"; do
  mkdir -p "$destination"
  cp -R "$root/skills/." "$destination/"
done
"""


def _pyproject(name: str) -> str:
    return f"""[project]
name = "{name}"
version = "0.1.0"
description = "{name} agent skill repository"
requires-python = ">=3.11"
"""


def _skill_file(name: str) -> str:
    return f"""---
name: {name}
description: "Use when the user asks for {name}."
---

# {name}

## Workflow

1. Confirm the requested outcome.
2. Perform the required work.
3. Verify the result before reporting it.
"""


def _brand_svg(name: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" '
        'viewBox="0 0 160 160">\n'
        '  <rect width="160" height="160" fill="#183153"/>\n'
        '  <text x="80" y="92" fill="#ffffff" font-family="sans-serif" '
        f'font-size="28" text-anchor="middle">{name[:8]}</text>\n'
        "</svg>\n"
    )


__all__ = ["PackageResult", "package_check", "publish_preflight", "scaffold_skill_repo"]
