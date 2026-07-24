from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from skill2.package import package_check, publish_preflight, scaffold_skill_repo

ROOT = Path(__file__).resolve().parents[1]


def _add_manifests(root: Path, version: str = "0.1.0") -> None:
    codex = root / ".codex-plugin"
    claude = root / ".claude-plugin"
    codex.mkdir()
    claude.mkdir()
    common = {
        "name": root.name,
        "version": version,
        "description": f"{root.name} skill repository.",
        "homepage": f"https://github.com/example/{root.name}",
        "repository": f"https://github.com/example/{root.name}",
        "license": "MIT",
    }
    (codex / "plugin.json").write_text(
        json.dumps({**common, "skills": "skills"}), encoding="utf-8"
    )
    (claude / "plugin.json").write_text(json.dumps(common), encoding="utf-8")
    (claude / "marketplace.json").write_text(
        json.dumps(
            {
                "name": f"{root.name}-marketplace",
                "description": f"{root.name} skill marketplace.",
                "owner": {"name": "Test"},
                "plugins": [
                    {
                        "name": root.name,
                        "description": common["description"],
                        "version": version,
                        "source": "./",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _make_publishable(root: Path) -> None:
    readme = root / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace(
            "npx skills add .", f"npx skills add test-owner/{root.name}"
        ),
        encoding="utf-8",
    )


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
        self.assertFalse((root / "README.zh.md").exists())
        self.assertFalse((root / "install.sh").exists())
        return root

    def test_scaffold_creates_lint_clean_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            result = package_check(root)
            self.assertFalse(result.has_errors, result.to_dict())
            self.assertEqual(result.schema_version, "1")
            self.assertEqual(result.to_dict()["issues"], [])

    def test_package_check_rejects_install_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            readme = root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "npx skills add .", "npx skills add OWNER/demo-skill"
                ),
                encoding="utf-8",
            )
            self.assertIn("P2P003", {issue.rule_id for issue in package_check(root).issues})

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
                if issue.rule_id == "P2RT001" and "runtime" in issue.message
            ]
            self.assertTrue(runtime_errors, result.to_dict())
            self.assertFalse(
                any(issue.rule_id == "P2R001" for issue in runtime_errors),
                "runtime integrity must not reuse repo-structure P2R001",
            )
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
                if issue.rule_id == "P2RT001" and "runtime" in issue.message
            ]
            self.assertTrue(runtime_errors, result.to_dict())
            self.assertNotIn("P2R001", {issue.rule_id for issue in runtime_errors})
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
            _add_manifests(root)
            path = root / ".claude-plugin" / "marketplace.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["plugins"][0]["version"] = "0.2.0"
            path.write_text(json.dumps(payload), encoding="utf-8")
            rules = {issue.rule_id for issue in package_check(root).issues}
            self.assertIn("P2M005", rules)

    def test_package_check_reports_bash_manifest_and_content_risks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            _add_manifests(root)
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
            _add_manifests(root)
            _make_publishable(root)
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

    def test_publish_preflight_allows_multiple_native_install_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            _make_publishable(root)
            self._commit(root)
            readme = root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8") + "\n```bash\npip install demo-skill\n```\n",
                encoding="utf-8",
            )
            result = publish_preflight(root)
            rules = {issue.rule_id for issue in result.issues}
            self.assertNotIn("P2P003", rules)
            self.assertIn("P2P005", rules)

    def test_publish_preflight_checks_localized_readme_only_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            _make_publishable(root)
            self._commit(root)
            self.assertFalse(publish_preflight(root).has_errors)

            (root / "README.zh.md").write_text(
                "# 中文\n\n## 安装\n\n```bash\nnpx skills add other/repo -g -a codex -y\n```\n",
                encoding="utf-8",
            )
            result = publish_preflight(root)
            self.assertIn("P2P003", {issue.rule_id for issue in result.issues})

    def test_publish_preflight_rejects_local_only_install_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            self._commit(root)
            self.assertIn("P2P003", {issue.rule_id for issue in publish_preflight(root).issues})

    def test_publish_preflight_rejects_chinese_readme_as_english_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.scaffold(Path(tmp))
            (root / "README.md").write_text(
                "# Skill2\n\n这是一个 Skill Library。\n\n```bash\n"
                "npx skills add test-owner/demo-skill -g -a codex -y\n```\n",
                encoding="utf-8",
            )
            self._commit(root)
            self.assertIn("P2P001", {issue.rule_id for issue in publish_preflight(root).issues})

    def test_public_readmes_native_install_surface(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh.md").read_text(encoding="utf-8")
        claude_commands = (
            "/plugin marketplace add blackblue-labs/skill2",
            "/plugin install skill2@skill2-marketplace",
        )
        codex_command = "npx skills add blackblue-labs/skill2 -g -a codex -y"
        offline_boundary = re.compile(
            r"(?is)uv run --script.*first run.*uv cache|uv run --script.*首次.*uv cache|"
            r"offline.*warm cache|离线.*预热|离线.*已有.*cache",
        )
        for text in (english, chinese):
            for command in claude_commands:
                self.assertIn(command, text)
            self.assertIn(codex_command, text)
            self.assertRegex(
                text,
                r"(?is)five self-contained skills|五个自包含\s*Skills",
            )
            self.assertRegex(
                text,
                offline_boundary,
                "README must state uv run --script + first-run cache / offline warm-cache boundary",
            )
            self.assertNotRegex(
                text,
                r"(?is)(searchable|available|listed)\s+(in|via|under)\s+/plugins|"
                r"/plugins\s+(marketplace\s+)?(lists?|includes?|has)\s+Skill2|"
                r"Skill2\s+is\s+(searchable|listed)\s+in\s+/plugins|"
                r"可在\s*/plugins\s*中搜索|已上架\s*/plugins|/plugins\s*可搜索",
            )
            self.assertNotRegex(
                text,
                r"(?is)installs?\s+six\s+Skill2\s+skills\s+and\s+the\s+helper\s+CLI|"
                r"helper\s+CLI|"
                r"安装六个\s*Skill2\s*Skills\s*和辅助\s*CLI|"
                r"辅助\s*CLI",
            )
            self.assertNotIn("skill2-publish", text)
        for command in (*claude_commands, codex_command):
            self.assertEqual(
                english.count(command),
                chinese.count(command),
                f"install command must be byte-identical in both READMEs: {command}",
            )
            self.assertGreaterEqual(english.count(command), 1)

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
