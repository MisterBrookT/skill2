from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_SAFE_SYSTEM_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
_PACKAGE_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ExecutionResult:
    exit_code: int
    duration_ms: int
    final_message: str
    events: tuple[dict[str, Any], ...]
    commands: tuple[str, ...]
    activations: dict[str, str]
    evidence: tuple[str, ...]
    workspace: str
    changed_files: tuple[str, ...]
    error: str | None = None


@dataclass(frozen=True)
class TrialSkill2Cli:
    bin_dir: Path
    wrapper: Path
    tool_source: Path

    def isolation_fields(self) -> dict[str, Any]:
        return {
            "skill2_cli_available": True,
            "skill2_cli_bin": str(self.wrapper),
            "skill2_tool_source": str(self.tool_source),
            "path_excludes_user_local_bin": True,
        }


def run_codex(
    *,
    prompt: str,
    skill_dirs: tuple[Path, ...],
    fixture: Path | None,
    artifact_dir: Path,
    timeout: int,
    model: str | None,
) -> ExecutionResult:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="skill2-") as temp_value:
        temp = Path(temp_value)
        codex_home = temp / "codex-home"
        isolated_home = temp / "home"
        workspace = temp / "work"
        codex_home.mkdir()
        isolated_home.mkdir()
        workspace.mkdir()
        skill2_cli = _install_trial_skill2_cli(temp)
        _copy_auth(codex_home)
        installed = _install_skills(skill_dirs, codex_home / "skills")
        if fixture:
            shutil.copytree(fixture, workspace, dirs_exist_ok=True)
        before = _workspace_hashes(workspace)

        events_path = artifact_dir / "events.jsonl"
        stderr_path = artifact_dir / "stderr.log"
        last_path = temp / "last-message.txt"
        codex_executable = _codex_executable()
        command = [
            str(codex_executable),
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--json",
            "--skip-git-repo-check",
            "-C",
            str(workspace),
            "--sandbox",
            "workspace-write",
            "--output-last-message",
            str(last_path),
        ]
        if model:
            command.extend(["--model", model])
        command.append(prompt)
        env = os.environ.copy()
        env.pop("SKILL2_CODEX_BIN", None)
        env.pop("SKILL2_CLAUDE_BIN", None)
        env["HOME"] = str(isolated_home)
        env["CODEX_HOME"] = str(codex_home)
        env["PATH"] = _safe_path(skill2_cli.bin_dir)
        command, host_guard = _guard_host_home(command, Path.home(), codex_executable)
        sandbox_mode = "workspace-write"
        if host_guard == "macos-seatbelt":
            sandbox_index = command.index("--sandbox")
            command[sandbox_index : sandbox_index + 2] = [
                "--dangerously-bypass-approvals-and-sandbox"
            ]
            sandbox_mode = "outer-macos-seatbelt"

        error: str | None = None
        process = subprocess.Popen(
            command,
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            exit_code = 124
            error = f"codex timed out after {timeout}s"

        manifest = {
            "runner": "codex",
            "codex_version": _codex_version(),
            "model": model,
            "timeout": timeout,
            "sandbox": sandbox_mode,
            "skills": sorted(installed),
            "fixture": str(fixture) if fixture else None,
            "command": command[:-1],
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "isolation": {
                "ephemeral": True,
                "ignore_user_config": True,
                "ignore_rules": True,
                "temporary_home": True,
                "sanitized_path": True,
                "host_home_guard": host_guard,
                "system_prompt_control": "harness-managed",
                **skill2_cli.isolation_fields(),
            },
        }
        (artifact_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        events_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        events = _parse_events(stdout)
        commands = tuple(_event_commands(events))
        activations, evidence = detect_activations(events, installed)
        final_message = last_path.read_text(encoding="utf-8") if last_path.exists() else ""
        (artifact_dir / "last-message.txt").write_text(final_message, encoding="utf-8")
        after = _workspace_hashes(workspace)
        changed_files = tuple(
            sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        )
        preserved_workspace = artifact_dir / "workspace"
        shutil.copytree(workspace, preserved_workspace, dirs_exist_ok=True)

    duration_ms = round((time.monotonic() - started) * 1000)
    if exit_code != 0 and error is None:
        error = f"codex exited {exit_code}"
    return ExecutionResult(
        exit_code=exit_code,
        duration_ms=duration_ms,
        final_message=final_message,
        events=events,
        commands=commands,
        activations=activations,
        evidence=evidence,
        workspace=str(preserved_workspace),
        changed_files=changed_files,
        error=error,
    )


def detect_activations(
    events: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    installed: dict[str, Path],
) -> tuple[dict[str, str], tuple[str, ...]]:
    activations: dict[str, str] = {}
    evidence: list[str] = []
    for event in events:
        item = event.get("item")
        command = item.get("command", "") if isinstance(item, dict) else ""
        for name, skill_file in installed.items():
            if isinstance(command, str) and str(skill_file) in command:
                activations[name] = "medium"
                marker = f"exact SKILL.md read: {name}"
                if marker not in evidence:
                    evidence.append(marker)
            if _explicit_skill_event(event, name):
                activations[name] = "high"
                marker = f"explicit skill event: {name}"
                if marker not in evidence:
                    evidence.append(marker)
    return activations, tuple(evidence)


def _explicit_skill_event(event: dict[str, Any], name: str) -> bool:
    item = event.get("item")
    if not isinstance(item, dict):
        return False
    item_type = str(item.get("type") or "").lower()
    item_name = str(item.get("name") or item.get("skill") or "")
    return "skill" in item_type and item_name == name


def _copy_auth(codex_home: Path) -> None:
    source_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    auth = source_home / "auth.json"
    if not auth.is_file():
        raise RuntimeError(f"Codex auth not found: {auth}")
    shutil.copy2(auth, codex_home / "auth.json")
    installation_id = source_home / "installation_id"
    if installation_id.is_file():
        shutil.copy2(installation_id, codex_home / "installation_id")


def _codex_executable() -> Path:
    configured = os.environ.get("SKILL2_CODEX_BIN")
    candidate = Path(configured).expanduser() if configured else shutil.which("codex")
    if not candidate:
        raise RuntimeError("codex executable not found")
    executable = Path(candidate).resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError(f"codex executable is not runnable: {executable}")
    return executable


def _install_trial_skill2_cli(temp: Path) -> TrialSkill2Cli:
    tool_source = temp / "tool-src"
    package_dest = tool_source / "skill2"
    tool_source.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        _PACKAGE_ROOT,
        package_dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.py[co]", "*.so"),
    )
    bin_dir = temp / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "skill2"
    wrapper.write_text(
        "#!/bin/sh\n"
        f"export PYTHONPATH={shlex.quote(str(tool_source))}\n"
        f"exec {shlex.quote(sys.executable)} -m skill2.cli \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return TrialSkill2Cli(bin_dir=bin_dir, wrapper=wrapper, tool_source=tool_source)


def _safe_path(bin_dir: Path) -> str:
    return f"{bin_dir}{os.pathsep}{_SAFE_SYSTEM_PATH}"


def _python_runtime_read_roots(agent_executable: Path) -> tuple[Path, ...]:
    roots: list[Path] = []
    for candidate in (
        agent_executable.resolve().parent,
        Path(sys.executable).resolve().parent,
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
    ):
        resolved = candidate.resolve()
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _guard_host_home(
    command: list[str], host_home: Path, agent_executable: Path
) -> tuple[list[str], str]:
    sandbox = shutil.which("sandbox-exec")
    if sys.platform == "darwin" and sandbox:
        home = _seatbelt_string(str(host_home.resolve()))
        allows = "".join(
            f'(allow file-read* (subpath "{_seatbelt_string(str(root))}"))'
            for root in _python_runtime_read_roots(agent_executable)
        )
        profile = (
            "(version 1)"
            "(allow default)"
            f'(deny file-read* file-write* (subpath "{home}"))'
            f"{allows}"
        )
        return [sandbox, "-p", profile, *command], "macos-seatbelt"
    if os.environ.get("SKILL2_ALLOW_UNGUARDED") == "1":
        return command, "explicitly-unguarded"
    raise RuntimeError(
        "host filesystem isolation unavailable; set SKILL2_ALLOW_UNGUARDED=1 to opt out"
    )


def _seatbelt_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _install_skills(skill_dirs: tuple[Path, ...], root: Path) -> dict[str, Path]:
    root.mkdir(parents=True)
    installed: dict[str, Path] = {}
    for source in skill_dirs:
        source = source.expanduser().resolve()
        skill_file = source / "SKILL.md"
        if not skill_file.is_file():
            raise ValueError(f"missing SKILL.md: {source}")
        target = root / source.name
        shutil.copytree(source, target)
        installed[source.name] = target / "SKILL.md"
    return installed


def _parse_events(stdout: str) -> tuple[dict[str, Any], ...]:
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return tuple(events)


def _event_commands(events: tuple[dict[str, Any], ...]) -> list[str]:
    commands: list[str] = []
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        command = item.get("command")
        if isinstance(command, str) and command not in commands:
            commands.append(command)
    return commands


def _workspace_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


@lru_cache(maxsize=1)
def _codex_version() -> str:
    completed = subprocess.run(
        ["codex", "--version"],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    return completed.stdout.strip() or completed.stderr.strip() or "unknown"
