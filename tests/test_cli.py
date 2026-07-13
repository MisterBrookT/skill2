from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "skill2.cli", *args],
        cwd=cwd or ROOT,
        env={"PYTHONPATH": str(ROOT / "src")},
        text=True,
        capture_output=True,
        check=False,
    )


class Skill2CliTest(unittest.TestCase):
    def test_scaffold_creates_lint_clean_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_cli(
                "scaffold",
                "skill",
                "demo-skill",
                "-o",
                str(root / "skills"),
                "--description",
                "Use when the user asks to demo a skill trigger.",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            skill = root / "skills" / "demo-skill" / "SKILL.md"
            self.assertTrue(skill.exists())
            body = skill.read_text(encoding="utf-8")
            self.assertIn("Use when the user asks to demo a skill trigger.", body)
            self.assertIn("## 决策", body)
            self.assertIn("原则", body)
            self.assertNotIn("## 流程", body)
            self.assertNotRegex(body, r"(?m)^1\.\s")

            lint = run_cli("lint", str(root / "skills"), "--json")
            self.assertEqual(lint.returncode, 0, lint.stderr)
            payload = json.loads(lint.stdout)
            self.assertEqual(payload["checked"], 1)
            self.assertEqual(payload["issues"], [])

    def test_scaffold_default_description_is_trigger_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_cli("scaffold", "skill", "demo-skill", "-o", str(root / "skills"))
            self.assertEqual(result.returncode, 0, result.stderr)
            body = (root / "skills" / "demo-skill" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn('description: "Use when the user needs demo-skill."', body)
            self.assertNotIn("## 流程", body)
            self.assertNotRegex(body, r"(?m)^1\.\s")

    def test_lint_reports_name_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "right-name"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: wrong-name
description: "bad"
---

# right-name

body long enough for lint to skip short-body warning.
""",
                encoding="utf-8",
            )
            result = run_cli("lint", str(skill_dir), "--json")
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            messages = [issue["message"] for issue in payload["issues"]]
            self.assertIn(
                "Directory name 'right-name' must match skill name 'wrong-name'",
                messages,
            )

    def test_lint_reports_local_path_and_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "risky-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: risky-skill
description: "bad"
---

# risky-skill

Do not use /Users/alice/private.
token: sk-testtoken123456
""",
                encoding="utf-8",
            )
            result = run_cli("lint", str(skill_dir), "--json")
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            messages = [issue["message"] for issue in payload["issues"]]
            self.assertIn("contains machine-local absolute path", messages)
            self.assertIn("possible secret or credential text", messages)

    def test_lint_warns_non_executable_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "script-skill"
            scripts = skill_dir / "scripts"
            scripts.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: script-skill
description: "script"
---

# script-skill

Run script when deterministic work is needed.
""",
                encoding="utf-8",
            )
            script = scripts / "run.sh"
            script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            result = run_cli("lint", str(skill_dir), "--json")
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            messages = [issue["message"] for issue in payload["issues"]]
            self.assertIn("script is not executable", messages)

    def test_scan_skips_runtime_package_resources_as_scripts(self) -> None:
        """Generated _runtime + dotfiles are package resources, not entry scripts."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "bundled-skill"
            scripts = skill_dir / "scripts"
            runtime = scripts / "_runtime" / "skill2"
            nested = scripts / "helpers"
            runtime.mkdir(parents=True)
            nested.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: bundled-skill
description: "Use when testing runtime bundle script inventory."
---

# bundled-skill

Run scripts/run for deterministic work.
""",
                encoding="utf-8",
            )
            run = scripts / "run"
            run.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
            run.chmod(0o755)
            (runtime / "module.py").write_text("# package resource\nx = 1\n", encoding="utf-8")
            (scripts / ".runtime-manifest.json").write_text("{}\n", encoding="utf-8")
            helper = nested / "tool.py"
            helper.write_text("print('nested')\n", encoding="utf-8")
            helper.chmod(0o755)

            scan = run_cli("scan", str(skill_dir), "--json")
            self.assertEqual(scan.returncode, 0, scan.stderr)
            payload = json.loads(scan.stdout)
            skill = payload["skills"][0]
            self.assertEqual(
                skill["scripts"],
                ["scripts/helpers/tool.py", "scripts/run"],
            )
            self.assertNotIn("scripts/_runtime/skill2/module.py", skill["scripts"])
            self.assertNotIn("scripts/.runtime-manifest.json", skill["scripts"])

            lint = run_cli("lint", str(skill_dir), "--json")
            self.assertEqual(lint.returncode, 0, lint.stderr)
            lint_payload = json.loads(lint.stdout)
            paths = [issue["path"] for issue in lint_payload["issues"]]
            messages = [issue["message"] for issue in lint_payload["issues"]]
            self.assertFalse(
                any("_runtime" in path for path in paths),
                lint_payload["issues"],
            )
            self.assertNotIn("script is not executable", messages)

    def test_scan_emits_stable_inventory(self) -> None:
        result = run_cli("scan", "skills", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "1")
        self.assertEqual(len(payload["skills"]), 6)
        publish = next(skill for skill in payload["skills"] if skill["name"] == "skill2-publish")
        self.assertEqual(publish["scope"], "project")
        self.assertEqual(len(publish["hash"]), 64)
        self.assertGreater(publish["body_tokens"], 0)

    def test_scan_parses_yaml_and_markdown_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "demo"
            references = skill_dir / "references"
            references.mkdir(parents=True)
            (references / "guide.md").write_text("guide\n", encoding="utf-8")
            (skill_dir / "SKILL.md").write_text(
                """---
name: demo
description: >-
  Use when multiline YAML metadata
  must parse correctly.
---

# demo

Read [guide](references/guide.md#top) before doing deterministic work.
""",
                encoding="utf-8",
            )
            result = run_cli("scan", str(skill_dir), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            skill = payload["skills"][0]
            self.assertEqual(
                skill["description"],
                "Use when multiline YAML metadata must parse correctly.",
            )
            self.assertEqual(skill["references"], ["references/guide.md"])

    def test_lint_emits_sarif(self) -> None:
        result = run_cli("lint", "skills", "--format", "sarif")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["version"], "2.1.0")
        self.assertEqual(payload["runs"][0]["tool"]["driver"]["name"], "skill2")

    def test_scaffold_skill_repo_passes_package_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scaffold = run_cli("scaffold", "skill-repo", "demo-repo", "-o", tmp)
            self.assertEqual(scaffold.returncode, 0, scaffold.stderr)
            result = run_cli("package-check", str(Path(tmp) / "demo-repo"), "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["issues"], [])

    def test_visualize_renders_terminal_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / ".codex"
            codex.mkdir()
            result = run_cli(
                "visualize",
                "--codex",
                str(codex),
                "--skills",
                "skills",
                "--tests",
                str(root / "missing-tests"),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Skill Library", result.stdout)
            self.assertIn("zero-direct", result.stdout)
            self.assertIn("Delete candidates", result.stdout)
            self.assertIn("Downgrade candidates", result.stdout)
            self.assertNotIn("lifecycle", result.stdout.lower())

    def test_visualize_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex = Path(tmp) / ".codex"
            codex.mkdir()
            result = run_cli("visualize", "--codex", str(codex), "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], "1")
            self.assertIn("skills", payload)

    def test_suggest_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex = Path(tmp) / ".codex"
            codex.mkdir()
            result = run_cli(
                "suggest",
                "--codex",
                str(codex),
                "--skills",
                "skills",
                "--tests",
                str(Path(tmp) / "missing-tests"),
                "--json",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["schema_version"], "1")

    def test_cli_import_is_lazy(self) -> None:
        code = (
            "import json, sys; import skill2.cli; "
            "print(json.dumps(sorted(name for name in sys.modules "
            "if name in {'skill2.tester','skill2.usage','skill2.package'})))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            env={"PYTHONPATH": str(ROOT / "src")},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])


if __name__ == "__main__":
    unittest.main()
