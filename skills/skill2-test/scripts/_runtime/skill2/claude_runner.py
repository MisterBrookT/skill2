from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .codex_runner import (
    ExecutionResult,
    _guard_host_home,
    _install_skills,
    _install_trial_skill2_cli,
    _safe_path,
    _workspace_hashes,
)


def run_claude(
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
    with tempfile.TemporaryDirectory(prefix="skill2-claude-") as temp_value:
        temp = Path(temp_value)
        isolated_home = temp / "home"
        workspace = temp / "work"
        isolated_home.mkdir()
        workspace.mkdir()
        skill2_cli = _install_trial_skill2_cli(temp)
        settings_copied = _copy_settings(isolated_home)
        installed = _install_skills(skill_dirs, isolated_home / ".claude" / "skills")
        if fixture:
            shutil.copytree(fixture, workspace, dirs_exist_ok=True)
        before = _workspace_hashes(workspace)
        executable = _claude_executable()
        command = [
            str(executable),
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
        if model:
            command.extend(["--model", model])
        command.append(prompt)
        env = _isolated_env(isolated_home, skill2_cli.bin_dir)
        command, host_guard = _guard_host_home(command, Path.home(), executable)
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
        error: str | None = None
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
            error = f"claude timed out after {timeout}s"

        events = _parse_events(stdout)
        activations, evidence = detect_activations(events, installed)
        commands = _event_commands(events)
        final_message = _final_message(events)
        events_path = artifact_dir / "events.jsonl"
        events_path.write_text(stdout, encoding="utf-8")
        (artifact_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        (artifact_dir / "last-message.txt").write_text(final_message, encoding="utf-8")
        manifest = {
            "runner": "claude",
            "model": model,
            "timeout": timeout,
            "skills": sorted(installed),
            "fixture": str(fixture) if fixture else None,
            "command": command[:-1],
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "isolation": {
                "temporary_home": True,
                "temporary_claude_skills": True,
                "settings_copied": settings_copied,
                "sanitized_path": True,
                "host_home_guard": host_guard,
                **skill2_cli.isolation_fields(),
            },
        }
        (artifact_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        after = _workspace_hashes(workspace)
        changed_files = tuple(
            sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        )
        preserved_workspace = artifact_dir / "workspace"
        shutil.copytree(workspace, preserved_workspace, dirs_exist_ok=True)

    duration_ms = round((time.monotonic() - started) * 1000)
    if exit_code != 0 and error is None:
        error = f"claude exited {exit_code}"
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
    events: tuple[dict[str, Any], ...], installed: dict[str, Path]
) -> tuple[dict[str, str], tuple[str, ...]]:
    activations: dict[str, str] = {}
    evidence: list[str] = []
    for tool in _tool_uses(events):
        if tool.get("name") != "Read":
            continue
        payload = tool.get("input")
        if not isinstance(payload, dict):
            continue
        path = payload.get("file_path") or payload.get("path")
        if not isinstance(path, str):
            continue
        for name, skill_file in installed.items():
            if path == str(skill_file):
                activations[name] = "medium"
                marker = f"exact SKILL.md read: {name}"
                if marker not in evidence:
                    evidence.append(marker)
    return activations, tuple(evidence)


def _copy_settings(isolated_home: Path) -> bool:
    source = Path.home() / ".claude" / "settings.json"
    if not source.is_file():
        return False
    destination = isolated_home / ".claude" / "settings.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def _claude_executable() -> Path:
    configured = os.environ.get("SKILL2_CLAUDE_BIN")
    candidate = Path(configured).expanduser() if configured else shutil.which("claude")
    if not candidate:
        raise RuntimeError("claude executable not found")
    executable = Path(candidate).resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError(f"claude executable is not runnable: {executable}")
    return executable


def _isolated_env(home: Path, bin_dir: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("ANTHROPIC_", "CLAUDE_"))
        and key not in {"SKILL2_CLAUDE_BIN", "SKILL2_CODEX_BIN"}
    }
    env["HOME"] = str(home)
    env["PATH"] = _safe_path(bin_dir)
    return env


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


def _tool_uses(value: object) -> tuple[dict[str, Any], ...]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("type") == "tool_use" and isinstance(value.get("name"), str):
            found.append(value)
        for child in value.values():
            found.extend(_tool_uses(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.extend(_tool_uses(child))
    return tuple(found)


def _event_commands(events: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    commands: list[str] = []
    for tool in _tool_uses(events):
        if tool.get("name") != "Bash" or not isinstance(tool.get("input"), dict):
            continue
        command = tool["input"].get("command")
        if isinstance(command, str):
            commands.append(command)
    return tuple(commands)


def _final_message(events: tuple[dict[str, Any], ...]) -> str:
    for event in reversed(events):
        result = event.get("result")
        if isinstance(result, str):
            return result
    texts: list[str] = []
    for event in events:
        for item in _text_blocks(event):
            texts.append(item)
    return texts[-1] if texts else ""


def _text_blocks(value: object) -> tuple[str, ...]:
    texts: list[str] = []
    if isinstance(value, dict):
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            texts.append(value["text"])
        for child in value.values():
            texts.extend(_text_blocks(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            texts.extend(_text_blocks(child))
    return tuple(texts)
