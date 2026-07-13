from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"
BARE_SKILL2_CMD = re.compile(
    r"(^|`)skill2 (scan|lint|test|package-check|publish-check|usage|suggest|visualize|scaffold)"
)
LOCAL_RUN_FORM = re.compile(
    r"uv run --script <skill-dir>/scripts/run -- "
    r"(scan|lint|test|package-check|publish-check|usage|suggest|visualize|scaffold)\b"
)


def source_skills() -> list[str]:
    return sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir())


def fake_uv_env(root: Path, exit_code: int = 0) -> dict[str, str]:
    fake_bin = root / "fake-uv-bin"
    fake_bin.mkdir(exist_ok=True)
    log = root / "uv.log"
    uv = fake_bin / "uv"
    uv.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$SKILL2_TEST_UV_LOG\"\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    return {
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "SKILL2_TEST_UV_LOG": str(log),
    }


def path_without_uv() -> str:
    """PATH with no uv binary (install must not need global CLI tooling)."""
    return "/usr/bin:/bin:/usr/sbin:/sbin"


def run_install(
    home: Path,
    *args: str,
    stdin: str | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
):
    command = ["bash", str(INSTALL), *args] if stdin is None else ["bash", "-s", "--", *args]
    process_env = os.environ.copy()
    process_env["HOME"] = str(home)
    if env:
        process_env.update(env)
    return subprocess.run(
        command,
        cwd=cwd or ROOT,
        env=process_env,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


class InstallScriptTest(unittest.TestCase):
    def test_install_does_not_require_or_invoke_uv_tool_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = fake_uv_env(home)
            # Install must succeed with no uv on PATH at all.
            no_uv = run_install(home, "codex", env={"PATH": path_without_uv()})
            self.assertEqual(no_uv.returncode, 0, no_uv.stderr)
            destination = home / ".agents" / "skills"
            self.assertTrue((destination / "skill2-create" / "SKILL.md").is_file())
            self.assertNotIn("uv tool install", no_uv.stdout)
            self.assertNotIn("uv tool install", no_uv.stderr)
            self.assertNotIn("uv is required", no_uv.stderr)

            # With a logging fake uv present, install must never call it.
            home2 = Path(tmp) / "home2"
            home2.mkdir()
            with_fake = run_install(home2, "claude", env=env)
            self.assertEqual(with_fake.returncode, 0, with_fake.stderr)
            log = home / "uv.log"
            self.assertFalse(log.exists(), "install must never invoke uv")
            if log.exists():
                self.assertNotIn("tool install", log.read_text(encoding="utf-8"))

    def test_installed_skills_include_executable_local_run_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_install(home, "codex", env={"PATH": path_without_uv()})
            self.assertEqual(result.returncode, 0, result.stderr)
            destination = home / ".agents" / "skills"
            for name in source_skills():
                skill = destination / name
                run = skill / "scripts" / "run"
                runtime = skill / "scripts" / "_runtime" / "skill2"
                self.assertTrue(run.is_file(), f"missing {run}")
                self.assertTrue(
                    os.access(run, os.X_OK),
                    f"scripts/run must be executable: {run}",
                )
                self.assertTrue(
                    (runtime / "__init__.py").is_file(),
                    f"missing bundled runtime: {runtime}",
                )
                self.assertTrue((skill / "SKILL.md").is_file())

    def test_skill_docs_do_not_require_global_skill2_command(self) -> None:
        offenders: list[str] = []
        local_examples = 0
        doc_paths = list((ROOT / "skills").glob("*/SKILL.md"))
        doc_paths.extend((ROOT / "skills").glob("*/references/**/*.md"))
        for path in sorted(doc_paths):
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if BARE_SKILL2_CMD.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{lineno}:{line.strip()}")
                if LOCAL_RUN_FORM.search(line):
                    local_examples += 1
        self.assertEqual(
            offenders,
            [],
            "bare global skill2 commands remain in skill docs:\n" + "\n".join(offenders),
        )
        self.assertGreater(
            local_examples,
            0,
            "skill docs must show uv run --script <skill-dir>/scripts/run -- <command>",
        )

    def test_codex_installs_lists_statuses_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = fake_uv_env(home)
            first = run_install(home, "codex", env=env)
            self.assertEqual(first.returncode, 0, first.stderr)
            destination = home / ".agents" / "skills"
            self.assertIn(f"target: {destination}", first.stdout)
            for name in source_skills():
                self.assertIn(f"  {name}: new", first.stdout)
                self.assertTrue((destination / name / "SKILL.md").exists())

            provenance = (destination / ".skill2-install-provenance").read_text(encoding="utf-8")
            self.assertIn("source_url=", provenance)
            self.assertIn("ref=", provenance)
            self.assertIn("tree_sha=", provenance)
            self.assertNotIn("test-secret-value", provenance)

            second = run_install(
                home,
                "codex",
                env={**env, "SKILL2_SECRET": "test-secret-value"},
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            for name in source_skills():
                self.assertIn(f"  {name}: unchanged", second.stdout)
            self.assertEqual(list(destination.glob(".skill2-staging.*")), [])
            # Installer must not call uv tool install (skills carry local runtime).
            log = home / "uv.log"
            self.assertFalse(log.exists() or (log.exists() and log.read_text(encoding="utf-8")))

    def test_rejects_multiple_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_install(Path(tmp), "all", "codex")
            self.assertEqual(result.returncode, 2)
            self.assertIn("usage:", result.stderr)

    def test_dry_run_reports_replace_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = fake_uv_env(home)
            self.assertEqual(run_install(home, "codex", env=env).returncode, 0)
            destination = home / ".agents" / "skills"
            skill = source_skills()[0]
            installed = destination / skill / "SKILL.md"
            installed.write_text("changed\n", encoding="utf-8")

            result = run_install(home, "--dry-run", "codex")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"  {skill}: replace", result.stdout)
            self.assertIn("dry-run: no files changed", result.stdout)
            self.assertEqual(installed.read_text(encoding="utf-8"), "changed\n")

    def test_replace_requires_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = fake_uv_env(home)
            self.assertEqual(run_install(home, "codex", env=env).returncode, 0)
            destination = home / ".agents" / "skills"
            skill = source_skills()[0]
            installed = destination / skill / "SKILL.md"
            installed.write_text("local change\n", encoding="utf-8")

            blocked = run_install(home, "codex", env=env)
            self.assertEqual(blocked.returncode, 1)
            self.assertIn("rerun with --force", blocked.stderr)
            self.assertEqual(installed.read_text(encoding="utf-8"), "local change\n")

            forced = run_install(home, "codex", "--force", env=env)
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertNotEqual(installed.read_text(encoding="utf-8"), "local change\n")

    def test_retired_skills_require_force_then_are_removed(self) -> None:
        for retired_name in ("skill2-build", "skill2-prune"):
            with self.subTest(retired=retired_name):
                with tempfile.TemporaryDirectory() as tmp:
                    home = Path(tmp)
                    env = fake_uv_env(home)
                    destination = home / ".agents" / "skills"
                    retired = destination / retired_name
                    retired.mkdir(parents=True)
                    (retired / "SKILL.md").write_text("legacy\n", encoding="utf-8")

                    blocked = run_install(home, "codex", env=env)
                    self.assertEqual(blocked.returncode, 1)
                    self.assertIn(f"{retired_name}: retired", blocked.stdout)
                    self.assertTrue(retired.exists())

                    forced = run_install(home, "codex", "--force", env=env)
                    self.assertEqual(forced.returncode, 0, forced.stderr)
                    self.assertFalse(retired.exists())
                    self.assertTrue((destination / "skill2-create" / "SKILL.md").is_file())
                    self.assertTrue(
                        (destination / "skill2-visualize" / "SKILL.md").is_file()
                    )

    def test_all_installs_both_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_install(home, "all", env=fake_uv_env(home))
            self.assertEqual(result.returncode, 0, result.stderr)
            for relative in (".agents/skills", ".claude/skills"):
                destination = home / relative
                self.assertTrue((destination / ".skill2-install-provenance").exists())
                installed = sorted(
                    path.name for path in destination.glob("skill2-*") if path.is_dir()
                )
                self.assertEqual(installed, source_skills())

    def test_claude_installs_is_idempotent_and_requires_force_for_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = fake_uv_env(home)
            first = run_install(home, "claude", env=env)
            self.assertEqual(first.returncode, 0, first.stderr)
            destination = home / ".claude" / "skills"
            self.assertTrue((destination / ".skill2-install-provenance").is_file())
            self.assertEqual(
                sorted(path.name for path in destination.glob("skill2-*") if path.is_dir()),
                source_skills(),
            )

            second = run_install(home, "claude", env=env)
            self.assertEqual(second.returncode, 0, second.stderr)
            skill = source_skills()[0]
            installed = destination / skill / "SKILL.md"
            installed.write_text("local change\n", encoding="utf-8")
            blocked = run_install(home, "claude", env=env)
            self.assertEqual(blocked.returncode, 1)
            self.assertEqual(installed.read_text(encoding="utf-8"), "local change\n")
            forced = run_install(home, "claude", "--force", env=env)
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertNotEqual(installed.read_text(encoding="utf-8"), "local change\n")

    def test_pipe_execution_clones_when_script_has_no_local_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_git = fake_bin / "git"
            fake_git.write_text(
                "#!/usr/bin/env bash\n"
                "if [ \"$1\" = clone ]; then\n"
                "  for arg; do dest=\"$arg\"; done\n"
                "  mkdir -p \"$dest/skills/demo\"\n"
                "  printf '%s\\n' demo > \"$dest/skills/demo/SKILL.md\"\n"
                "  exit 0\n"
                "fi\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake_git.chmod(0o755)
            env = fake_uv_env(root)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            result = run_install(
                home,
                "codex",
                stdin=INSTALL.read_text(encoding="utf-8"),
                env=env,
                cwd=root,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / ".agents" / "skills" / "demo" / "SKILL.md").exists())

    def test_missing_uv_still_installs_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_install(home, "codex", env={"PATH": path_without_uv()})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("uv is required", result.stderr)
            self.assertNotIn("cli:", result.stdout)
            self.assertTrue((home / ".agents" / "skills" / "skill2-create" / "SKILL.md").is_file())

    def test_fake_uv_failure_is_ignored_because_uv_is_not_invoked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_install(home, "codex", env=fake_uv_env(home, exit_code=1))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("could not install the skill2 CLI", result.stderr)
            self.assertTrue((home / ".agents" / "skills" / "skill2-create" / "SKILL.md").is_file())
            self.assertFalse((home / "uv.log").exists())

    def test_dry_run_does_not_preview_or_run_cli_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = fake_uv_env(home)
            result = run_install(home, "claude", "--dry-run", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("cli:", result.stdout)
            self.assertNotIn("uv tool install", result.stdout)
            self.assertIn("dry-run: no files changed", result.stdout)
            self.assertFalse((home / "uv.log").exists())
            self.assertFalse((home / ".claude").exists())


if __name__ == "__main__":
    unittest.main()
