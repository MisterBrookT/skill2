#!/usr/bin/env python3
"""Clean-install smoke for install.sh / npx / Claude marketplace paths.

Uses temporary HOME + temporary source copy. Detaches source before running
installed Skill scripts. Checkpoints under .skill2/install-smoke/<run-id>/.
No tag, release, registry, or PyPI side effects.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ALL_MODES = ("install-sh", "npx", "claude")
SKILL_NAMES = (
    "skill2-audit",
    "skill2-create",
    "skill2-package",
    "skill2-publish",
    "skill2-test",
    "skill2-visualize",
)
REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_ROOT = REPO_ROOT / ".skill2" / "install-smoke"

_TOKEN_RE = re.compile(
    r"(?i)(\bsk-[A-Za-z0-9_-]{8,}\b|\bghp_[A-Za-z0-9]{20,}\b|"
    r"\bBearer\s+\S+|\bAuthorization:\s*\S+)"
)
_PROMPT_RE = re.compile(r"(?i)\bprompt\b\s*:?[^\n]*")
_TRANSCRIPT_RE = re.compile(r"(?i)\btranscript\b[^\n]*")


def build_npx_command(source: Path) -> list[str]:
    return ["npx", "--yes", "skills", "add", str(source), "-g", "-a", "codex", "-y"]


def build_claude_marketplace_add(source: Path) -> list[str]:
    return ["claude", "plugin", "marketplace", "add", str(source)]


def build_claude_plugin_install() -> list[str]:
    return ["claude", "plugin", "install", "skill2@skill2-marketplace"]


def sanitize_text(text: str, *paths: str) -> str:
    out = text
    for raw in paths:
        if not raw:
            continue
        out = out.replace(raw, "<path>")
        try:
            out = out.replace(str(Path(raw).expanduser().resolve()), "<path>")
        except OSError:
            pass
    home = str(Path.home())
    out = out.replace(home, "<real-home>")
    try:
        out = out.replace(str(Path.home().resolve()), "<real-home>")
    except OSError:
        pass
    out = _TOKEN_RE.sub("<redacted-token>", out)
    out = _PROMPT_RE.sub("<redacted>", out)
    out = _TRANSCRIPT_RE.sub("<redacted>", out)
    return out


def normalize_modes(modes: list[str]) -> list[str]:
    wanted: set[str] = set()
    for mode in modes:
        if mode == "all":
            wanted.update(ALL_MODES)
        elif mode in ALL_MODES:
            wanted.add(mode)
        else:
            raise SystemExit(f"unknown mode: {mode}")
    # Stable product order; dedupe by mode name.
    return [mode for mode in ALL_MODES if mode in wanted]


def _sanitize_obj(value: Any, *paths: str) -> Any:
    if isinstance(value, str):
        return sanitize_text(value, *paths)
    if isinstance(value, list):
        return [_sanitize_obj(item, *paths) for item in value]
    if isinstance(value, dict):
        return {str(k): _sanitize_obj(v, *paths) for k, v in value.items()}
    return value


def write_mode_checkpoint(run_dir: Path, mode: str, payload: dict[str, Any]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f"{mode}.json"
    clean = _sanitize_obj(payload, str(Path.home()))
    path.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def is_mode_complete(run_dir: Path, mode: str) -> bool:
    path = run_dir / f"{mode}.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return data.get("status") == "completed"


def modes_to_run(modes: list[str], run_dir: Path, *, resume: bool) -> list[str]:
    ordered = normalize_modes(modes)
    if not resume:
        return ordered
    return [mode for mode in ordered if not is_mode_complete(run_dir, mode)]


def materialize_source(repo: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    shutil.copytree(repo / "skills", dest / "skills", ignore=ignore)
    shutil.copy2(repo / "install.sh", dest / "install.sh")
    shutil.copytree(repo / ".claude-plugin", dest / ".claude-plugin", ignore=ignore)
    return dest


def detach_source(source: Path) -> None:
    """Rename then remove temp source so installed scripts cannot reach it."""
    if not source.exists():
        return
    gone = source.with_name(source.name + ".detached")
    if gone.exists():
        shutil.rmtree(gone)
    source.rename(gone)
    shutil.rmtree(gone)


def _run(
    cmd: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _require_skills(root: Path) -> list[str]:
    missing = [name for name in SKILL_NAMES if not (root / name / "SKILL.md").is_file()]
    if missing:
        raise RuntimeError(f"missing installed skills: {', '.join(missing)}")
    return list(SKILL_NAMES)


def _run_skill_script(
    run_script: Path,
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    if not run_script.is_file():
        raise RuntimeError(f"missing skill script: {run_script.name}")
    cmd = ["uv", "run", "--script", str(run_script), "--", *args]
    return _run(cmd, env=env, cwd=cwd)


def _scrub_result(
    proc: subprocess.CompletedProcess[str],
    *paths: str,
) -> dict[str, Any]:
    return {
        "exit": proc.returncode,
        "stdout": sanitize_text(proc.stdout or "", *paths)[-4000:],
        "stderr": sanitize_text(proc.stderr or "", *paths)[-4000:],
    }


def run_mode(
    mode: str,
    *,
    run_dir: Path,
    repo_root: Path,
    source_root: Path,
    home: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    started = datetime.now(UTC).isoformat()
    path_keys = (str(home), str(source_root), str(repo_root), str(Path.home()))
    payload: dict[str, Any] = {
        "mode": mode,
        "status": "running",
        "started_at": started,
        "detached": False,
        "skills": [],
    }
    try:
        if mode == "install-sh":
            detail = _mode_install_sh(source_root, home, env, path_keys)
        elif mode == "npx":
            detail = _mode_npx(source_root, home, env, path_keys)
        elif mode == "claude":
            detail = _mode_claude(source_root, home, env, path_keys)
        else:
            raise ValueError(f"unknown mode: {mode}")
        payload.update(detail)
        payload["status"] = "completed"
        payload["finished_at"] = datetime.now(UTC).isoformat()
        write_mode_checkpoint(run_dir, mode, payload)
        return payload
    except Exception as exc:  # noqa: BLE001 — surface as mode failure
        payload["status"] = "failed"
        payload["error"] = sanitize_text(str(exc), *path_keys)
        payload["finished_at"] = datetime.now(UTC).isoformat()
        write_mode_checkpoint(run_dir, mode, payload)
        return payload


def _mode_install_sh(
    source: Path,
    home: Path,
    env: dict[str, str],
    path_keys: tuple[str, ...],
) -> dict[str, Any]:
    install = source / "install.sh"
    if not install.is_file():
        raise RuntimeError("install.sh missing from temp source")
    proc = _run(["bash", str(install), "all"], env=env, cwd=source)
    if proc.returncode != 0:
        raise RuntimeError(
            f"install.sh failed: {sanitize_text(proc.stderr or proc.stdout or '', *path_keys)}"
        )
    agents = home / ".agents" / "skills"
    skills = _require_skills(agents)
    claude_skills = home / ".claude" / "skills"
    if claude_skills.is_dir():
        _require_skills(claude_skills)

    detach_source(source)
    if source.exists():
        raise RuntimeError("temp source still present after detach")

    out = home / "smoke-scaffold-out"
    out.mkdir(parents=True, exist_ok=True)
    run = agents / "skill2-create" / "scripts" / "run"
    skill_proc = _run_skill_script(
        run,
        ["scaffold", "skill", "smoke-demo", "-o", str(out)],
        env=env,
        cwd=home,
    )
    if skill_proc.returncode != 0:
        raise RuntimeError(
            "skill2-create failed: "
            + sanitize_text(skill_proc.stderr or skill_proc.stdout or "", *path_keys)
        )
    created = out / "smoke-demo" / "SKILL.md"
    if not created.is_file():
        raise RuntimeError("scaffold did not create SKILL.md")
    return {
        "skills": skills,
        "detached": True,
        "skill_created": True,
        "install": _scrub_result(proc, *path_keys),
        "skill_command": _scrub_result(skill_proc, *path_keys),
        "skill_command_summary": "scaffold skill smoke-demo",
    }


def _mode_npx(
    source: Path,
    home: Path,
    env: dict[str, str],
    path_keys: tuple[str, ...],
) -> dict[str, Any]:
    cmd = build_npx_command(source)
    proc = _run(cmd, env=env, cwd=home)
    if proc.returncode != 0:
        raise RuntimeError(
            f"npx skills add failed: {sanitize_text(proc.stderr or proc.stdout or '', *path_keys)}"
        )
    agents = home / ".agents" / "skills"
    skills = _require_skills(agents)

    detach_source(source)
    if source.exists():
        raise RuntimeError("temp source still present after detach")

    run = agents / "skill2-visualize" / "scripts" / "run"
    skill_proc = _run_skill_script(
        run,
        [
            "visualize",
            "--skills",
            str(agents),
            "--codex",
            "-",
            "--claude",
            "-",
            "--tests",
            str(home / "empty-tests"),
        ],
        env=env,
        cwd=home,
    )
    if skill_proc.returncode != 0:
        raise RuntimeError(
            "skill2-visualize failed: "
            + sanitize_text(skill_proc.stderr or skill_proc.stdout or "", *path_keys)
        )
    combined = (skill_proc.stdout or "") + (skill_proc.stderr or "")
    if not combined.strip():
        raise RuntimeError("skill2-visualize produced empty output")
    return {
        "skills": skills,
        "detached": True,
        "install": _scrub_result(proc, *path_keys),
        "skill_command": _scrub_result(skill_proc, *path_keys),
        "skill_command_summary": "visualize inventory",
    }


def _mode_claude(
    source: Path,
    home: Path,
    env: dict[str, str],
    path_keys: tuple[str, ...],
) -> dict[str, Any]:
    add = _run(build_claude_marketplace_add(source), env=env, cwd=home)
    if add.returncode != 0:
        raise RuntimeError(
            f"claude marketplace add failed: "
            f"{sanitize_text(add.stderr or add.stdout or '', *path_keys)}"
        )
    install = _run(build_claude_plugin_install(), env=env, cwd=home)
    if install.returncode != 0:
        raise RuntimeError(
            f"claude plugin install failed: "
            f"{sanitize_text(install.stderr or install.stdout or '', *path_keys)}"
        )

    cache = home / ".claude" / "plugins" / "cache"
    runs = sorted(cache.glob("**/skills/skill2-create/scripts/run"))
    if not runs:
        raise RuntimeError("claude install missing skill2-create/scripts/run")
    create_run = runs[0]
    skill_root = create_run.parents[1]  # .../skills/skill2-create
    skills_dir = skill_root.parent  # .../skills
    found = [p.name for p in skills_dir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()]
    missing = [name for name in SKILL_NAMES if name not in found]
    if missing:
        raise RuntimeError(f"claude install missing skills: {', '.join(missing)}")

    detach_source(source)
    if source.exists():
        raise RuntimeError("temp source still present after detach")

    out = home / "smoke-scaffold-out"
    out.mkdir(parents=True, exist_ok=True)
    skill_proc = _run_skill_script(
        create_run,
        ["scaffold", "skill", "smoke-demo", "-o", str(out)],
        env=env,
        cwd=home,
    )
    if skill_proc.returncode != 0:
        raise RuntimeError(
            "installed skill script failed: "
            + sanitize_text(skill_proc.stderr or skill_proc.stdout or "", *path_keys)
        )
    if not (out / "smoke-demo" / "SKILL.md").is_file():
        raise RuntimeError("claude detached scaffold did not create SKILL.md")
    return {
        "skills": list(SKILL_NAMES),
        "detached": True,
        "skill_created": True,
        "marketplace_add": _scrub_result(add, *path_keys),
        "plugin_install": _scrub_result(install, *path_keys),
        "skill_command": _scrub_result(skill_proc, *path_keys),
        "skill_command_summary": "scaffold skill smoke-demo",
    }


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def _resolve_run_dir(run_id: str | None, *, resume: bool) -> Path:
    CHECKPOINT_ROOT.mkdir(parents=True, exist_ok=True)
    if run_id:
        path = CHECKPOINT_ROOT / run_id
        if resume and not path.is_dir():
            raise SystemExit(f"resume run-id not found: {run_id}")
        path.mkdir(parents=True, exist_ok=True)
        return path
    if resume:
        runs = sorted(
            (p for p in CHECKPOINT_ROOT.iterdir() if p.is_dir()),
            key=lambda p: p.name,
        )
        if not runs:
            raise SystemExit("no prior install-smoke runs to resume")
        return runs[-1]
    path = CHECKPOINT_ROOT / _new_run_id()
    path.mkdir(parents=True, exist_ok=True)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Skill2 clean-install smoke (install-sh / npx / claude)",
    )
    parser.add_argument(
        "--mode",
        default="all",
        choices=[*ALL_MODES, "all"],
        help="which install path to smoke",
    )
    parser.add_argument("--run-id", default=None, help="checkpoint run id")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip modes already completed under run-id",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="checkout to copy as install source",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    run_dir = _resolve_run_dir(args.run_id, resume=args.resume)
    modes = modes_to_run([args.mode], run_dir, resume=args.resume)

    summary: dict[str, Any] = {
        "run_id": run_dir.name,
        "modes_requested": normalize_modes([args.mode]),
        "modes_run": [],
        "modes_skipped": [
            m
            for m in normalize_modes([args.mode])
            if m not in modes and is_mode_complete(run_dir, m)
        ],
        "results": {},
    }

    failed = False
    for mode in modes:
        with tempfile.TemporaryDirectory(prefix=f"skill2-smoke-{mode}-") as tmp:
            base = Path(tmp)
            home = base / "home"
            home.mkdir()
            source = base / "src"
            materialize_source(repo_root, source)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env.pop("PYTHONPATH", None)
            # Avoid leaking real user config into tools that respect XDG.
            env["XDG_CONFIG_HOME"] = str(home / ".config")
            env["XDG_CACHE_HOME"] = str(home / ".cache")
            env["XDG_DATA_HOME"] = str(home / ".local" / "share")
            result = run_mode(
                mode,
                run_dir=run_dir,
                repo_root=repo_root,
                source_root=source,
                home=home,
                env=env,
            )
            summary["modes_run"].append(mode)
            summary["results"][mode] = {
                "status": result.get("status"),
                "detached": result.get("detached"),
                "skills": result.get("skills"),
                "error": result.get("error"),
            }
            if result.get("status") != "completed":
                failed = True
                break

    summary["status"] = "failed" if failed else "completed"
    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        sanitize_text(json.dumps(summary, indent=2, ensure_ascii=False)) + "\n",
        encoding="utf-8",
    )
    print(f"install-smoke run_id={run_dir.name} status={summary['status']}")
    for mode, info in summary["results"].items():
        print(f"  {mode}: {info.get('status')}")
    if summary["modes_skipped"]:
        print(f"  skipped: {', '.join(summary['modes_skipped'])}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
