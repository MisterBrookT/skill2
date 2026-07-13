from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"


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
            self.assertEqual(
                (home / "uv.log").read_text(encoding="utf-8").splitlines(),
                [
                    f"tool install --force --reinstall --refresh {ROOT}",
                    f"tool install --force --reinstall --refresh {ROOT}",
                ],
            )

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

    def test_missing_uv_stops_before_skills_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_install(home, "codex", env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"})
            self.assertEqual(result.returncode, 1)
            self.assertIn("uv is required", result.stderr)
            self.assertFalse((home / ".agents").exists())

    def test_failed_cli_install_stops_before_skills_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = run_install(home, "codex", env=fake_uv_env(home, exit_code=1))
            self.assertEqual(result.returncode, 1)
            self.assertIn("could not install the skill2 CLI", result.stderr)
            self.assertFalse((home / ".agents").exists())

    def test_dry_run_previews_cli_without_running_uv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = fake_uv_env(home)
            result = run_install(home, "claude", "--dry-run", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                f"cli: uv tool install --force --reinstall --refresh {ROOT}", result.stdout
            )
            self.assertFalse((home / "uv.log").exists())
            self.assertFalse((home / ".claude").exists())


if __name__ == "__main__":
    unittest.main()
