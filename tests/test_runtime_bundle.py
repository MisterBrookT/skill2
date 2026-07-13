from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fingerprint_real_skill_scripts() -> dict[str, tuple[int, int, str]]:
    """Hash tracked generated scripts under real checkout (regression guard)."""
    out: dict[str, tuple[int, int, str]] = {}
    for path in sorted(ROOT.glob("skills/*/scripts/**/*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(ROOT))
        st = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        out[rel] = (st.st_mtime_ns, st.st_size, digest)
    return out


def _make_temp_repo() -> tempfile.TemporaryDirectory[str]:
    """Canonical src + empty six skill dirs; sync only touches this tree."""
    tmp = tempfile.TemporaryDirectory()
    repo = Path(tmp.name)
    shutil.copytree(ROOT / "src" / "skill2", repo / "src" / "skill2")
    from skill2.bundle import RUNTIME_SPECS

    for skill_name in RUNTIME_SPECS:
        (repo / "skills" / skill_name).mkdir(parents=True)
    return tmp


class RuntimeBundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._scripts_before = _fingerprint_real_skill_scripts()

    def tearDown(self) -> None:
        after = _fingerprint_real_skill_scripts()
        self.assertEqual(
            self._scripts_before,
            after,
            "tests must not mutate real skills/*/scripts",
        )

    def test_sync_generates_run_manifest_and_minimal_runtime(self) -> None:
        from skill2.bundle import RUNTIME_SPECS, sync_skill_runtimes

        with _make_temp_repo() as tmp:
            repo = Path(tmp)
            written = sync_skill_runtimes(repo)
            self.assertTrue(written)

            create = repo / "skills" / "skill2-create" / "scripts"
            run = create / "run"
            manifest_path = create / ".runtime-manifest.json"
            runtime = create / "_runtime" / "skill2"

            self.assertTrue(run.is_file())
            self.assertTrue(os.access(run, os.X_OK), "scripts/run must be executable")
            self.assertTrue(manifest_path.is_file())
            self.assertTrue((runtime / "__init__.py").is_file())
            self.assertTrue((runtime / "models.py").is_file())
            self.assertTrue((runtime / "cli.py").is_file())
            self.assertTrue((runtime / "scaffold.py").is_file())
            self.assertFalse((runtime / "package.py").exists())
            self.assertFalse((runtime / "tester.py").exists())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            create_spec = RUNTIME_SPECS["skill2-create"]
            self.assertEqual(manifest["commands"], list(create_spec.commands))
            self.assertEqual(manifest["dependencies"], list(create_spec.dependencies))
            self.assertIn("files", manifest)
            for rel, meta in manifest["files"].items():
                self.assertIn("sha256", meta)
                self.assertIn("source", meta)
                self.assertFalse(
                    Path(meta["source"]).is_absolute(),
                    f"manifest source must be relative: {meta['source']}",
                )
                self.assertTrue(rel.startswith("skill2/"))

            text = run.read_text(encoding="utf-8")
            self.assertIn("uv run --script", text)
            self.assertIn("requires-python", text)
            self.assertIn("dependencies", text)
            self.assertIn("skill2.cli", text)

    def test_check_reports_source_hash_drift(self) -> None:
        from skill2.bundle import check_skill_runtimes, sync_skill_runtimes

        with _make_temp_repo() as tmp:
            repo = Path(tmp)
            sync_skill_runtimes(repo)
            self.assertEqual(check_skill_runtimes(repo), ())

            source = repo / "src" / "skill2" / "scaffold.py"
            original = source.read_text(encoding="utf-8")
            source.write_text(original + "\n# drift-marker\n", encoding="utf-8")
            stale = check_skill_runtimes(repo)
            self.assertTrue(stale)
            self.assertTrue(any("skill2-create" in path for path in stale))

            source.write_text(original, encoding="utf-8")
            sync_skill_runtimes(repo)
            self.assertEqual(check_skill_runtimes(repo), ())

    def test_check_reports_unexpected_runtime_file(self) -> None:
        from skill2.bundle import check_skill_runtimes, sync_skill_runtimes

        with _make_temp_repo() as tmp:
            repo = Path(tmp)
            sync_skill_runtimes(repo)
            self.assertEqual(check_skill_runtimes(repo), ())

            bogey = (
                repo
                / "skills"
                / "skill2-create"
                / "scripts"
                / "_runtime"
                / "skill2"
                / "package.py"
            )
            bogey.write_text("# unexpected extra\n", encoding="utf-8")
            stale = check_skill_runtimes(repo)
            self.assertTrue(stale)
            rel = bogey.relative_to(repo).as_posix()
            self.assertIn(rel, stale)
            # expected files still present must not be flagged alone as stale
            self.assertFalse(
                any(
                    path.endswith("skill2/scaffold.py")
                    or path.endswith("skill2/cli.py")
                    for path in stale
                ),
                stale,
            )

    def test_installed_create_runs_without_source_checkout(self) -> None:
        from skill2.bundle import sync_skill_runtimes

        checkout = str(ROOT.resolve())

        with _make_temp_repo() as tmp:
            repo = Path(tmp)
            sync_skill_runtimes(repo)
            create_src = repo / "skills" / "skill2-create"

            with tempfile.TemporaryDirectory() as install_tmp:
                install = Path(install_tmp)
                skill_copy = install / "skill2-create"
                shutil.copytree(create_src, skill_copy)
                out_skills = install / "skills"
                out_skills.mkdir()

                env = os.environ.copy()
                env["UV_OFFLINE"] = "1"
                env.pop("PYTHONPATH", None)

                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "--script",
                        str(skill_copy / "scripts" / "run"),
                        "--",
                        "scaffold",
                        "skill",
                        "demo",
                        "-o",
                        str(out_skills),
                    ],
                    cwd=install,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
                )
                skill_md = out_skills / "demo" / "SKILL.md"
                self.assertTrue(skill_md.is_file(), result.stdout)

                manifest = json.loads(
                    (skill_copy / "scripts" / ".runtime-manifest.json").read_text(
                        encoding="utf-8"
                    )
                )
                blob = json.dumps(manifest) + result.stdout + result.stderr
                self.assertNotIn(checkout, blob)
                self.assertNotIn(str(repo.resolve()), blob)

    def test_wrapper_rejects_command_outside_skill_contract(self) -> None:
        from skill2.bundle import sync_skill_runtimes

        with _make_temp_repo() as tmp:
            repo = Path(tmp)
            sync_skill_runtimes(repo)
            run = repo / "skills" / "skill2-create" / "scripts" / "run"
            result = subprocess.run(
                ["uv", "run", "--script", str(run), "--", "scan", "skills"],
                cwd=repo,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            combined = (result.stdout + result.stderr).lower()
            self.assertTrue(
                "scan" in combined or "allowed" in combined or "command" in combined,
                combined,
            )


if __name__ == "__main__":
    unittest.main()
