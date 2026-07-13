from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / "tools" / "smoke_install.py"
REAL_HOME = str(Path.home().resolve())
SKILL_NAMES = (
    "skill2-audit",
    "skill2-create",
    "skill2-package",
    "skill2-publish",
    "skill2-test",
    "skill2-visualize",
)


def load_smoke():
    if not SMOKE_PATH.is_file():
        raise unittest.SkipTest(f"missing {SMOKE_PATH}")
    spec = importlib.util.spec_from_file_location("smoke_install", SMOKE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["smoke_install"] = mod
    spec.loader.exec_module(mod)
    return mod


def write_exec(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


class SmokeInstallUnitTest(unittest.TestCase):
    def test_module_importable(self) -> None:
        self.assertTrue(SMOKE_PATH.is_file(), f"expected {SMOKE_PATH}")
        smoke = load_smoke()
        self.assertTrue(hasattr(smoke, "build_npx_command"))
        self.assertTrue(hasattr(smoke, "build_claude_marketplace_add"))
        self.assertTrue(hasattr(smoke, "build_claude_plugin_install"))
        self.assertTrue(hasattr(smoke, "main"))

    def test_npx_command_construction(self) -> None:
        smoke = load_smoke()
        source = Path("/tmp/skill2-src-fixture")
        cmd = smoke.build_npx_command(source)
        self.assertEqual(cmd[0], "npx")
        self.assertIn("skills", cmd)
        self.assertIn("add", cmd)
        self.assertIn(str(source), cmd)
        self.assertIn("-g", cmd)
        self.assertIn("codex", cmd)
        self.assertIn("-y", cmd)

    def test_claude_command_construction(self) -> None:
        smoke = load_smoke()
        source = Path("/tmp/skill2-src-fixture")
        add_cmd = smoke.build_claude_marketplace_add(source)
        install_cmd = smoke.build_claude_plugin_install()
        self.assertEqual(add_cmd[:3], ["claude", "plugin", "marketplace"])
        self.assertIn("add", add_cmd)
        self.assertIn(str(source), add_cmd)
        self.assertEqual(install_cmd, ["claude", "plugin", "install", "skill2@skill2-marketplace"])

    def test_sanitize_strips_real_home_and_secrets(self) -> None:
        smoke = load_smoke()
        tmp_home = Path("/tmp/fake-smoke-home")
        blob = (
            f"installed into {REAL_HOME}/.ssh/id_rsa "
            f"and temp {tmp_home}/.agents "
            "Authorization: Bearer sk-test-secret-token-value "
            "prompt: do not store me "
            "transcript line"
        )
        cleaned = smoke.sanitize_text(blob, REAL_HOME, str(tmp_home))
        self.assertNotIn(REAL_HOME, cleaned)
        self.assertNotIn(str(tmp_home), cleaned)
        self.assertNotIn("sk-test-secret-token-value", cleaned)
        self.assertNotIn("Bearer sk-", cleaned)
        self.assertNotIn("prompt:", cleaned.lower())
        self.assertNotIn("do not store me", cleaned)
        self.assertNotIn("transcript line", cleaned)

    def test_checkpoint_resume_skips_completed_not_failed(self) -> None:
        smoke = load_smoke()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-1"
            run_dir.mkdir()
            smoke.write_mode_checkpoint(
                run_dir,
                "install-sh",
                {"mode": "install-sh", "status": "completed", "skills": list(SKILL_NAMES)},
            )
            smoke.write_mode_checkpoint(
                run_dir,
                "npx",
                {"mode": "npx", "status": "failed", "error": "boom"},
            )
            self.assertTrue(smoke.is_mode_complete(run_dir, "install-sh"))
            self.assertFalse(smoke.is_mode_complete(run_dir, "npx"))
            self.assertFalse(smoke.is_mode_complete(run_dir, "claude"))
            modes = smoke.modes_to_run(["all"], run_dir, resume=True)
            self.assertEqual(modes, ["npx", "claude"])
            modes_no_resume = smoke.modes_to_run(["install-sh", "npx"], run_dir, resume=False)
            self.assertEqual(modes_no_resume, ["install-sh", "npx"])

    def test_dedupe_modes(self) -> None:
        smoke = load_smoke()
        self.assertEqual(
            smoke.normalize_modes(["npx", "npx", "install-sh", "all"]),
            ["install-sh", "npx", "claude"],
        )
        self.assertEqual(smoke.normalize_modes(["claude"]), ["claude"])

    def test_npx_mode_fake_detached_and_no_real_home_in_manifest(self) -> None:
        smoke = load_smoke()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "home"
            home.mkdir()
            source = base / "src"
            _materialize_minimal_source(source)
            run_dir = base / "run"
            run_dir.mkdir()
            fake_bin = base / "bin"
            fake_bin.mkdir()
            write_exec(
                fake_bin / "npx",
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "# args: --yes skills add <source> -g -a codex -y\n"
                "source=\"\"\n"
                "prev=\"\"\n"
                "for a in \"$@\"; do\n"
                "  if [ \"$prev\" = \"add\" ]; then source=\"$a\"; fi\n"
                "  prev=\"$a\"\n"
                "done\n"
                "dest=\"$HOME/.agents/skills\"\n"
                "mkdir -p \"$dest\"\n"
                "cp -R \"$source\"/skills/* \"$dest/\"\n"
                "printf 'Installed 6 skills\\n'\n",
            )
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env.pop("PYTHONPATH", None)

            result = smoke.run_mode(
                "npx",
                run_dir=run_dir,
                repo_root=ROOT,
                source_root=source,
                home=home,
                env=env,
            )
            self.assertEqual(result["status"], "completed", result)
            self.assertTrue(result.get("detached"))
            self.assertFalse(source.exists(), "temp source must be removed before skill run")
            for name in SKILL_NAMES:
                self.assertTrue((home / ".agents" / "skills" / name / "SKILL.md").is_file())

            ck = json.loads((run_dir / "npx.json").read_text(encoding="utf-8"))
            blob = json.dumps(ck)
            self.assertNotIn(REAL_HOME, blob)
            self.assertNotIn(str(home.resolve()), blob)
            self.assertNotIn(str(source.resolve()), blob)
            # no auth/settings dumps
            for needle in ("credentials", "api_key", "ANTHROPIC", "OPENAI_API_KEY"):
                self.assertNotIn(needle.lower(), blob.lower())

    def test_install_sh_mode_fake_detached_create(self) -> None:
        smoke = load_smoke()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "home"
            home.mkdir()
            source = base / "src"
            _materialize_minimal_source(source)
            # real install.sh from repo, skills from minimal
            shutil.copy2(ROOT / "install.sh", source / "install.sh")
            run_dir = base / "run"
            run_dir.mkdir()
            env = os.environ.copy()
            env["HOME"] = str(home)
            # Keep real PATH so `uv` (Skill script host) remains available.
            env.pop("PYTHONPATH", None)

            result = smoke.run_mode(
                "install-sh",
                run_dir=run_dir,
                repo_root=ROOT,
                source_root=source,
                home=home,
                env=env,
            )
            self.assertEqual(result["status"], "completed", result)
            self.assertTrue(result.get("detached"))
            self.assertFalse(source.exists())
            create = home / ".agents" / "skills" / "skill2-create" / "scripts" / "run"
            self.assertTrue(create.is_file())
            # scaffold output recorded without real home
            ck = json.loads((run_dir / "install-sh.json").read_text(encoding="utf-8"))
            self.assertNotIn(REAL_HOME, json.dumps(ck))
            self.assertEqual(ck["status"], "completed")
            self.assertTrue(ck.get("skill_created"))

    def test_claude_mode_fake_detached(self) -> None:
        smoke = load_smoke()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "home"
            home.mkdir()
            source = base / "src"
            _materialize_minimal_source(source)
            run_dir = base / "run"
            run_dir.mkdir()
            fake_bin = base / "bin"
            write_exec(
                fake_bin / "claude",
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "if [ \"${1:-}\" = plugin ] && [ \"${2:-}\" = marketplace ] "
                "&& [ \"${3:-}\" = add ]; then\n"
                "  src=\"$4\"\n"
                "  mkdir -p \"$HOME/.claude/plugins\"\n"
                "  printf '%s\\n' \"$src\" > \"$HOME/.claude/plugins/marketplace-src\"\n"
                "  printf 'added marketplace\\n'\n"
                "  exit 0\n"
                "fi\n"
                "if [ \"${1:-}\" = plugin ] && [ \"${2:-}\" = install ]; then\n"
                "  src=\"$(cat \"$HOME/.claude/plugins/marketplace-src\")\"\n"
                "  dest=\"$HOME/.claude/plugins/cache/skill2-marketplace/skill2/0.1.0\"\n"
                "  mkdir -p \"$dest\"\n"
                "  cp -R \"$src\"/skills \"$dest/skills\"\n"
                "  cp -R \"$src\"/.claude-plugin \"$dest/.claude-plugin\"\n"
                "  printf 'installed plugin\\n'\n"
                "  exit 0\n"
                "fi\n"
                "printf 'unexpected: %s\\n' \"$*\" >&2\n"
                "exit 2\n",
            )
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env.pop("PYTHONPATH", None)

            result = smoke.run_mode(
                "claude",
                run_dir=run_dir,
                repo_root=ROOT,
                source_root=source,
                home=home,
                env=env,
            )
            self.assertEqual(result["status"], "completed", result)
            self.assertTrue(result.get("detached"))
            self.assertFalse(source.exists())
            ck = json.loads((run_dir / "claude.json").read_text(encoding="utf-8"))
            blob = json.dumps(ck)
            self.assertNotIn(REAL_HOME, blob)
            self.assertEqual(ck["status"], "completed")


def _materialize_minimal_source(dest: Path) -> None:
    """Copy six skills + manifests; enough for install-sh / fake npx / fake claude."""
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "skills", dest / "skills")
    shutil.copytree(ROOT / ".claude-plugin", dest / ".claude-plugin")
    if (ROOT / "install.sh").is_file():
        shutil.copy2(ROOT / "install.sh", dest / "install.sh")


class SmokeInstallCliTest(unittest.TestCase):
    def test_cli_help_lists_modes(self) -> None:
        if not SMOKE_PATH.is_file():
            self.fail(f"missing {SMOKE_PATH}")
        result = subprocess.run(
            [sys.executable, str(SMOKE_PATH), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout + result.stderr
        for mode in ("install-sh", "npx", "claude", "all"):
            self.assertIn(mode, out)
        self.assertIn("--resume", out)


if __name__ == "__main__":
    unittest.main()
