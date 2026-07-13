from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from skill2.package import package_check, publish_preflight, scaffold_skill_repo

ROOT = Path(__file__).resolve().parents[1]


def _skill2_package_repo(tmp: Path) -> Path:
    """Packageable Skill2-marker repo with synced runtimes (temp only)."""
    from skill2.bundle import RUNTIME_SPECS, sync_skill_runtimes

    scaffold_skill_repo("skill2-mini", tmp)
    root = tmp / "skill2-mini"
    shutil.copytree(ROOT / "src" / "skill2", root / "src" / "skill2")
    shutil.rmtree(root / "skills")
    for name in RUNTIME_SPECS:
        skill_dir = root / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            (
                f"---\nname: {name}\ndescription: \"Use when testing {name}.\"\n---\n\n"
                f"# {name}\n\n## Workflow\n\n"
                "1. Confirm outcome.\n2. Perform work.\n3. Verify result.\n"
            ),
            encoding="utf-8",
        )
    sync_skill_runtimes(root)
    return root


class PackageTest(unittest.TestCase):
    def scaffold(self, directory: Path, name: str = "demo-skill") -> Path:
        created = scaffold_skill_repo(name, directory)
        root = directory / name
        self.assertIn(str(root / "skills" / name / "SKILL.md"), created)
        self.assertTrue((root / "install.sh").stat().st_mode & 0o111)
        return root

    def test_scaffold_creates_lint_clean_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            self.assertTrue((root / ".claude-plugin" / "plugin.json").is_file())
            marketplace = json.loads(
                (root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
            )
            self.assertEqual(marketplace["plugins"][0]["source"], "./")
            result = package_check(root)
            self.assertFalse(result.has_errors, result.to_dict())
            self.assertEqual(result.schema_version, "1")
            self.assertEqual(result.to_dict()["issues"], [])

    def test_package_check_rejects_stale_skill_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _skill2_package_repo(Path(tmp))
            source = root / "src" / "skill2" / "scaffold.py"
            source.write_text(
                source.read_text(encoding="utf-8") + "\n# package-check-drift\n",
                encoding="utf-8",
            )
            result = package_check(root)
            self.assertTrue(result.has_errors, result.to_dict())
            runtime_errors = [
                issue
                for issue in result.issues
                if issue.rule_id == "P2R001" and "runtime" in issue.message
            ]
            self.assertTrue(runtime_errors, result.to_dict())
            joined = " ".join(issue.path for issue in runtime_errors)
            self.assertTrue(
                "skill2-create" in joined or "runtime-manifest" in joined,
                joined,
            )

    def test_package_check_rejects_missing_referenced_run_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _skill2_package_repo(Path(tmp))
            run = root / "skills" / "skill2-create" / "scripts" / "run"
            self.assertTrue(run.is_file())
            run.unlink()
            result = package_check(root)
            self.assertTrue(result.has_errors, result.to_dict())
            runtime_errors = [
                issue
                for issue in result.issues
                if issue.rule_id == "P2R001" and "runtime" in issue.message
            ]
            self.assertTrue(runtime_errors, result.to_dict())
            joined = " ".join(f"{issue.path} {issue.message}" for issue in runtime_errors)
            self.assertIn("skill2-create", joined)
            self.assertTrue("run" in joined or "scripts" in joined, joined)

    def test_generic_skill_repo_without_runtime_bundle_still_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp), name="third-party-skill")
            self.assertFalse((root / "src" / "skill2" / "bundle.py").is_file())
            self.assertFalse(
                any(root.glob("skills/*/scripts/.runtime-manifest.json")),
            )
            result = package_check(root)
            self.assertFalse(result.has_errors, result.to_dict())
            self.assertEqual(
                [issue for issue in result.issues if issue.rule_id == "P2R001"],
                [],
            )

    def test_package_check_rejects_mismatched_claude_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            path = root / ".claude-plugin" / "marketplace.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["plugins"][0]["version"] = "0.2.0"
            path.write_text(json.dumps(payload), encoding="utf-8")
            rules = {issue.rule_id for issue in package_check(root).issues}
            self.assertIn("P2M005", rules)

    def test_package_check_reports_bash_manifest_and_content_risks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            install = root / "install.sh"
            install.write_text("if then\n", encoding="utf-8")
            manifest = root / ".codex-plugin" / "plugin.json"
            manifest.write_text("{not json", encoding="utf-8")
            risky = root / "skills" / "demo-skill" / "scripts" / "unsafe.sh"
            risky.parent.mkdir()
            risky.write_text(
                "API_KEY=super-secret-value\ncd /Users/alice/private\nrm -rf /\n",
                encoding="utf-8",
            )
            os.symlink(root / "README.md", root / "linked-readme")

            result = package_check(root)
            rules = {issue.rule_id for issue in result.issues}
            self.assertTrue({"P2B001", "P2M002", "P2R003", "P2S001", "P2S002", "P2S003"} <= rules)

    def test_publish_preflight_requires_consistent_version_and_clean_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            self._commit(root)
            result = publish_preflight(root)
            self.assertFalse(result.has_errors, result.to_dict())

            manifest = root / ".codex-plugin" / "plugin.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["version"] = "0.2.0"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            result = publish_preflight(root)
            rules = {issue.rule_id for issue in result.issues}
            self.assertIn("P2P004", rules)
            self.assertIn("P2P005", rules)

    def test_publish_preflight_rejects_multiple_install_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            self._commit(root)
            readme = root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8") + "\n```bash\npip install demo-skill\n```\n",
                encoding="utf-8",
            )
            result = publish_preflight(root)
            rules = {issue.rule_id for issue in result.issues}
            self.assertIn("P2P003", rules)

    @staticmethod
    def _commit(root: Path) -> None:
        for command in (
            ["git", "init", "-q", str(root)],
            ["git", "-C", str(root), "add", "."],
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Skill2 Test",
                "-c",
                "user.email=skill2@example.invalid",
                "commit",
                "-qm",
                "initial",
            ],
        ):
            subprocess.run(command, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
