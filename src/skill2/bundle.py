from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALWAYS_MODULES: tuple[str, ...] = ("__init__", "models")


@dataclass(frozen=True)
class RuntimeSpec:
    commands: tuple[str, ...]
    roots: tuple[str, ...]
    dependencies: tuple[str, ...]


RUNTIME_SPECS: dict[str, RuntimeSpec] = {
    "skill2-create": RuntimeSpec(("scaffold",), ("cli", "scaffold"), ()),
    "skill2-test": RuntimeSpec(
        ("test",),
        ("cli", "cases", "codex_runner", "claude_runner", "tester", "scan"),
        ("PyYAML>=6.0.2,<7", "markdown-it-py>=3.0,<5"),
    ),
    "skill2-package": RuntimeSpec(
        ("scaffold", "lint", "package-check"),
        ("cli", "package", "lint", "scan"),
        ("PyYAML>=6.0.2,<7", "markdown-it-py>=3.0,<5", "skills-ref>=0.1.1,<0.2"),
    ),
    "skill2-publish": RuntimeSpec(
        ("publish-check",),
        ("cli", "package", "lint", "scan"),
        ("PyYAML>=6.0.2,<7", "markdown-it-py>=3.0,<5", "skills-ref>=0.1.1,<0.2"),
    ),
    "skill2-audit": RuntimeSpec(
        ("scan", "lint"),
        ("cli", "lint", "scan"),
        ("PyYAML>=6.0.2,<7", "markdown-it-py>=3.0,<5", "skills-ref>=0.1.1,<0.2"),
    ),
    "skill2-visualize": RuntimeSpec(
        ("usage", "suggest", "visualize"),
        ("cli", "scan", "usage", "report", "suggest"),
        ("PyYAML>=6.0.2,<7", "markdown-it-py>=3.0,<5"),
    ),
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _module_path(src_root: Path, name: str) -> Path:
    return src_root / f"{name}.py"


def _module_level_relative_imports(source: str) -> frozenset[str]:
    tree = ast.parse(source)
    found: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level == 0:
            continue
        if node.module:
            found.add(node.module.split(".", 1)[0])
        else:
            for alias in node.names:
                found.add(alias.name.split(".", 1)[0])
    return frozenset(found)


def resolve_module_closure(src_root: Path, roots: tuple[str, ...]) -> tuple[str, ...]:
    pending = list(dict.fromkeys((*ALWAYS_MODULES, *roots)))
    resolved: list[str] = []
    seen: set[str] = set()
    while pending:
        name = pending.pop(0)
        if name in seen:
            continue
        path = _module_path(src_root, name)
        if not path.is_file():
            raise FileNotFoundError(f"missing skill2 module: {name} ({path})")
        seen.add(name)
        resolved.append(name)
        source = path.read_text(encoding="utf-8")
        for dep in sorted(_module_level_relative_imports(source)):
            if dep not in seen and _module_path(src_root, dep).is_file():
                pending.append(dep)
    return tuple(sorted(resolved))


def _manifest_payload(
    *,
    commands: tuple[str, ...],
    dependencies: tuple[str, ...],
    files: dict[str, dict[str, str]],
) -> dict[str, Any]:
    return {
        "commands": list(commands),
        "dependencies": list(dependencies),
        "files": {key: files[key] for key in sorted(files)},
    }


def build_manifest(
    repo_root: Path,
    skill_name: str,
    spec: RuntimeSpec,
    modules: tuple[str, ...],
) -> dict[str, Any]:
    files: dict[str, dict[str, str]] = {}
    for name in modules:
        source_rel = f"src/skill2/{name}.py"
        source_path = repo_root / source_rel
        digest = _sha256_bytes(source_path.read_bytes())
        files[f"skill2/{name}.py"] = {"sha256": digest, "source": source_rel}
    return _manifest_payload(
        commands=spec.commands,
        dependencies=spec.dependencies,
        files=files,
    )


def _render_dependencies_block(dependencies: tuple[str, ...]) -> str:
    if not dependencies:
        return "# dependencies = []"
    lines = ["# dependencies = ["]
    for dep in dependencies:
        lines.append(f'#   "{dep}",')
    lines.append("# ]")
    return "\n".join(lines)


def _render_run_script(spec: RuntimeSpec) -> str:
    deps_block = _render_dependencies_block(spec.dependencies)
    commands = ", ".join(repr(cmd) for cmd in spec.commands)
    return f"""#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
{deps_block}
# ///
from __future__ import annotations

import sys
from pathlib import Path

_ALLOWED = frozenset({{{commands}}})
_RUNTIME = Path(__file__).resolve().parent / "_runtime"


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--":
        args = args[1:]
    if not args or args[0] not in _ALLOWED:
        allowed = ", ".join(sorted(_ALLOWED))
        got = args[0] if args else "<missing>"
        print(
            f"skill2 runtime: command {{got!r}} not allowed; allowed: {{allowed}}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    sys.path.insert(0, str(_RUNTIME))
    from skill2.cli import main as cli_main

    cli_main(args)


if __name__ == "__main__":
    main()
"""


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _expected_runtime_paths(repo_root: Path, skill_name: str) -> Path:
    return repo_root / "skills" / skill_name / "scripts"


def sync_one_skill(repo_root: Path, skill_name: str, spec: RuntimeSpec) -> tuple[Path, ...]:
    src_root = repo_root / "src" / "skill2"
    scripts = _expected_runtime_paths(repo_root, skill_name)
    runtime_pkg = scripts / "_runtime" / "skill2"
    modules = resolve_module_closure(src_root, spec.roots)

    if scripts.exists():
        runtime_root = scripts / "_runtime"
        if runtime_root.exists():
            shutil.rmtree(runtime_root)
    runtime_pkg.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for name in modules:
        src = _module_path(src_root, name)
        dest = runtime_pkg / f"{name}.py"
        shutil.copy2(src, dest)
        written.append(dest)

    manifest = build_manifest(repo_root, skill_name, spec, modules)
    manifest_path = scripts / ".runtime-manifest.json"
    _write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    written.append(manifest_path)

    run_path = scripts / "run"
    _write_text(run_path, _render_run_script(spec))
    _make_executable(run_path)
    written.append(run_path)

    return tuple(written)


def sync_skill_runtimes(repo_root: Path) -> tuple[Path, ...]:
    repo_root = repo_root.resolve()
    written: list[Path] = []
    for skill_name, spec in sorted(RUNTIME_SPECS.items()):
        written.extend(sync_one_skill(repo_root, skill_name, spec))
    return tuple(written)


def _current_manifest(repo_root: Path, skill_name: str, spec: RuntimeSpec) -> dict[str, Any]:
    src_root = repo_root / "src" / "skill2"
    modules = resolve_module_closure(src_root, spec.roots)
    return build_manifest(repo_root, skill_name, spec, modules)


def check_skill_runtimes(repo_root: Path) -> tuple[str, ...]:
    repo_root = repo_root.resolve()
    stale: list[str] = []
    for skill_name, spec in sorted(RUNTIME_SPECS.items()):
        scripts = _expected_runtime_paths(repo_root, skill_name)
        run_path = scripts / "run"
        manifest_path = scripts / ".runtime-manifest.json"
        runtime_pkg = scripts / "_runtime" / "skill2"

        markers = (
            str(run_path.relative_to(repo_root)),
            str(manifest_path.relative_to(repo_root)),
            str(runtime_pkg.relative_to(repo_root)),
        )

        if not run_path.is_file() or not manifest_path.is_file() or not runtime_pkg.is_dir():
            stale.extend(markers)
            continue

        try:
            on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            stale.append(str(manifest_path.relative_to(repo_root)))
            continue

        expected = _current_manifest(repo_root, skill_name, spec)
        if on_disk != expected:
            stale.append(str(manifest_path.relative_to(repo_root)))
            continue

        for rel, meta in expected["files"].items():
            dest = scripts / "_runtime" / rel
            if not dest.is_file():
                stale.append(str(dest.relative_to(repo_root)))
                continue
            if _sha256_bytes(dest.read_bytes()) != meta["sha256"]:
                stale.append(str(dest.relative_to(repo_root)))

        expected_run = _render_run_script(spec)
        if run_path.read_text(encoding="utf-8") != expected_run:
            stale.append(str(run_path.relative_to(repo_root)))
        elif not os.access(run_path, os.X_OK):
            stale.append(str(run_path.relative_to(repo_root)))

    # stable unique order
    return tuple(dict.fromkeys(stale))
