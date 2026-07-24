# Marketplace-first Install Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every installed Skill2 Skill carry its deterministic runtime so Claude marketplace, `npx skills add`, and `install.sh` deliver complete capability without a global `skill2` CLI install.

**Architecture:** `src/skill2/` remains canonical Python source. A deterministic bundler copies each Skill's minimal import closure into `skills/<name>/scripts/_runtime/`, generates a PEP 723 `scripts/run`, and records source hashes. Package checks reject stale bundles; native install paths copy only self-contained Skill directories.

**Tech Stack:** Python 3.11+, uv, PEP 723, unittest, argparse, Claude plugin manifests, Agent Skills directories.

## Global Constraints

- Skills are product; top-level Python CLI is contributor tooling only.
- Installed Skills must not access repository `src/`, `.venv`, or a global `skill2` executable.
- `src/skill2/` is canonical; generated `_runtime/` files are never edited manually.
- Skill bodies remain harness-neutral; adapters own Claude/Codex differences.
- User runtime dependency is `uv`; no PyPI package install is required.
- Claude marketplace is primary. Codex uses `npx skills add` until curated marketplace listing exists.
- `install.sh` copies Skills only; keep dry-run, conflict detection, atomic replacement.
- Package and publish checks have no remote writes.
- Workers do not commit or push. Main agent verifies and commits each task.
- Use TDD: observe each new test fail for missing behavior before implementation.

---

### Task 1: Make CLI imports bundle-safe

**Files:**
- Modify: `src/skill2/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: existing `skill2.cli.main(argv: list[str] | None) -> None`.
- Produces: same public CLI; command implementation modules imported only inside selected handlers.

- [ ] **Step 1: Write failing lazy-import test**

Add a subprocess test that imports `skill2.cli`, then asserts heavy command modules are absent:

```python
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
```

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=src uv run python -m unittest tests.test_cli.Skill2CliTest.test_cli_import_is_lazy
```

Expected: FAIL; current module imports `tester`, `usage`, and `package` at import time.

- [ ] **Step 3: Move command imports into handlers**

Keep stdlib and `models` imports at module scope. Import command modules inside `_cmd_scaffold`, `_cmd_scan`, `_cmd_lint`, `_cmd_test`, `_cmd_package_check`, `_usage_from_args`, `_cmd_suggest`, and `_cmd_visualize`. Split `_cmd_scaffold` imports by `args.kind` so `scaffold skill` does not import `package`.

- [ ] **Step 4: Verify GREEN and regression**

```bash
PYTHONPATH=src uv run python -m unittest tests.test_cli
uv run ruff check src/skill2/cli.py tests/test_cli.py
```

Expected: CLI tests pass; Ruff exits 0.

- [ ] **Step 5: Main review and commit**

```bash
git add src/skill2/cli.py tests/test_cli.py
git commit -m "lazy load commands"
```

---

### Task 2: Generate self-contained Skill runtimes

**Files:**
- Create: `src/skill2/bundle.py`
- Create: `tools/sync_skill_runtime.py`
- Create: `tests/test_runtime_bundle.py`
- Create/generated: `skills/*/scripts/run`
- Create/generated: `skills/*/scripts/_runtime/skill2/*.py`
- Create/generated: `skills/*/scripts/.runtime-manifest.json`

**Interfaces:**
- Produces `RuntimeSpec(commands: tuple[str, ...], roots: tuple[str, ...], dependencies: tuple[str, ...])`.
- Produces `RUNTIME_SPECS: dict[str, RuntimeSpec]` for six Skills.
- Produces `sync_skill_runtimes(repo_root: Path) -> tuple[Path, ...]`.
- Produces `check_skill_runtimes(repo_root: Path) -> tuple[str, ...]`; empty tuple means current.
- `tools/sync_skill_runtime.py --check` exits 1 and prints stale paths; normal mode rewrites generated files.

- [ ] **Step 1: Write failing bundle tests**

Cover:

```python
def test_sync_generates_run_manifest_and_minimal_runtime(): ...
def test_check_reports_source_hash_drift(): ...
def test_installed_create_runs_without_source_checkout(): ...
def test_wrapper_rejects_command_outside_skill_contract(): ...
```

The detached smoke copies only `skills/skill2-create`, sets `UV_OFFLINE=1`, runs:

```bash
uv run --script <copy>/scripts/run -- scaffold skill demo -o <tmp>/skills
```

Assert generated `SKILL.md` exists and no path under original checkout appears in manifest or output.

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH=src uv run python -m unittest tests.test_runtime_bundle
```

Expected: import/file-not-found failure because bundler and Skill scripts do not exist.

- [ ] **Step 3: Implement runtime specs and closure**

Use these command contracts:

```python
RUNTIME_SPECS = {
    "skill2-create": RuntimeSpec(("scaffold",), ("cli", "scaffold"), ()),
    "skill2-test": RuntimeSpec(
        ("test",),
        ("cli", "cases", "codex_runner", "claude_runner", "tester", "scan"),
        ("PyYAML>=6.0.2,<7", "markdown-it-py>=3.0,<5"),
    ),
    "skill2-package": RuntimeSpec(
        ("scaffold", "lint", "package-check"),
        ("cli", "package", "lint", "scan"),
        ("PyYAML>=6.0.2,<7", "markdown-it-py>=3.0,<5", "skills-ref>=0.1.1,<0.2"),
    ),
    "skill2-publish": RuntimeSpec(
        ("publish-check",),
        ("cli", "package", "lint", "scan"),
        ("PyYAML>=6.0.2,<7", "markdown-it-py>=3.0,<5", "skills-ref>=0.1.1,<0.2"),
    ),
    "skill2-audit": RuntimeSpec(
        ("scan", "lint"),
        ("cli", "lint", "scan"),
        ("PyYAML>=6.0.2,<7", "markdown-it-py>=3.0,<5", "skills-ref>=0.1.1,<0.2"),
    ),
    "skill2-visualize": RuntimeSpec(
        ("usage", "suggest", "visualize"),
        ("cli", "scan", "usage", "report", "suggest"),
        ("PyYAML>=6.0.2,<7", "markdown-it-py>=3.0,<5"),
    ),
}
```

Always include `__init__.py` and `models.py`. Parse module-level relative imports with `ast`; recursively copy local closure. Ignore function-local lazy imports unless their module is listed as a root. Generate stable sorted JSON manifest with source path, SHA-256, dependencies, and commands.

- [ ] **Step 4: Generate restricted PEP 723 wrappers**

Each `scripts/run`:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [...]
# ///
```

It inserts `scripts/_runtime` into `sys.path`, rejects a first argument outside its allowed commands, then calls `skill2.cli.main()` with remaining arguments. Mark executable.

- [ ] **Step 5: Generate repository artifacts and verify GREEN**

```bash
PYTHONPATH=src uv run python tools/sync_skill_runtime.py
PYTHONPATH=src uv run python -m unittest tests.test_runtime_bundle
PYTHONPATH=src uv run python tools/sync_skill_runtime.py --check
uv run ruff check src/skill2/bundle.py tools/sync_skill_runtime.py tests/test_runtime_bundle.py
```

Expected: all pass; `--check` prints no stale files.

- [ ] **Step 6: Main review and commit**

```bash
git add src/skill2/bundle.py tools/sync_skill_runtime.py tests/test_runtime_bundle.py skills/*/scripts
git commit -m "bundle skill runtimes"
```

---

### Task 3: Enforce runtime integrity in package checks

**Files:**
- Modify: `src/skill2/package.py`
- Modify: `tests/test_package.py`
- Modify: `tests/test_runtime_bundle.py`

**Interfaces:**
- Consumes `check_skill_runtimes(repo_root: Path) -> tuple[str, ...]`.
- Adds package rule `P2R001` for missing or stale generated runtime.
- Generic third-party repositories without `src/skill2/bundle.py` remain valid; runtime integrity gate activates only when `.runtime-manifest.json` exists or repo declares Skill2 runtime bundles.

- [ ] **Step 1: Write failing integrity tests**

Add tests for:

```python
def test_package_check_rejects_stale_skill_runtime(): ...
def test_package_check_rejects_missing_referenced_run_script(): ...
def test_generic_skill_repo_without_runtime_bundle_still_passes(): ...
```

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH=src uv run python -m unittest tests.test_package tests.test_runtime_bundle
```

Expected: stale/missing runtime tests fail because package check ignores bundles.

- [ ] **Step 3: Implement `P2R001`**

When checking Skill2 source repo, call `check_skill_runtimes`. Convert each stale path into `Severity.ERROR`, rule `P2R001`. Existing script/link checks remain authoritative for generic repositories.

- [ ] **Step 4: Verify GREEN**

```bash
PYTHONPATH=src uv run python -m unittest tests.test_package tests.test_runtime_bundle
uv run skill2 package-check .
```

Expected: tests pass; repository reports zero errors.

- [ ] **Step 5: Main review and commit**

```bash
git add src/skill2/package.py tests/test_package.py tests/test_runtime_bundle.py
git commit -m "check runtime bundles"
```

---

### Task 4: Make Skills and installer independent of global CLI

**Files:**
- Modify: `skills/skill2-create/SKILL.md`
- Modify: `skills/skill2-test/SKILL.md`
- Modify: `skills/skill2-package/SKILL.md`
- Modify: `skills/skill2-publish/SKILL.md`
- Modify: `skills/skill2-audit/SKILL.md`
- Modify: `skills/skill2-visualize/SKILL.md`
- Modify: `skills/skill2-visualize/references/lifecycle-suggestions.md`
- Modify: `install.sh`
- Modify: `tests/test_install.py`

**Interfaces:**
- Skill command form: `uv run --script <skill-dir>/scripts/run -- <command> <args>`.
- `install.sh` installs only Skill directories and provenance; it never invokes `uv tool install`.

- [ ] **Step 1: Write failing installer and documentation tests**

Add assertions:

```python
def test_install_does_not_require_or_invoke_uv_tool_install(): ...
def test_installed_skills_include_executable_local_run_scripts(): ...
def test_skill_docs_do_not_require_global_skill2_command(): ...
```

The first test runs with PATH lacking uv and expects install success. The third scans command lines and rejects bare `skill2 ` invocations.

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH=src uv run python -m unittest tests.test_install tests.test_runtime_bundle
```

Expected: current installer requires uv tool install; Skill docs contain bare `skill2` commands.

- [ ] **Step 3: Update Skill command examples**

Use one variable-neutral path placeholder:

```bash
uv run --script <skill-dir>/scripts/run -- visualize --skills <library> --codex ~/.codex
```

Do not add harness-specific prose to Skill bodies. Keep create free of behavior trials; test owns trials.

- [ ] **Step 4: Remove CLI installation from `install.sh`**

Delete uv presence check and `uv tool install`. Preserve target selection, dry-run, conflicts, retired Skill cleanup, staging, atomic replacement, provenance.

- [ ] **Step 5: Verify GREEN**

```bash
bash -n install.sh
PYTHONPATH=src uv run python -m unittest tests.test_install tests.test_runtime_bundle
rg -n '(^|`)skill2 (scan|lint|test|package-check|publish-check|usage|suggest|visualize|scaffold)' skills
```

Expected: tests pass; `rg` returns no bare global CLI dependency.

- [ ] **Step 6: Regenerate runtimes and commit**

```bash
PYTHONPATH=src uv run python tools/sync_skill_runtime.py
git add install.sh skills tests/test_install.py
git commit -m "make skills self contained"
```

---

### Task 5: Rewrite public install and packaging contract

**Files:**
- Modify: `README.md`
- Modify: `README.zh.md`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `.codex-plugin/plugin.json`
- Modify: `src/skill2/package.py`
- Modify: `tests/test_package.py`
- Modify: `skills/skill2-package/SKILL.md`
- Modify: `skills/skill2-publish/SKILL.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/CURRENT_STATUS.md`

**Interfaces:**
- README primary Claude commands:

```text
/plugin marketplace add blackblue-labs/skill2
/plugin install skill2@skill2-marketplace
```

- README current Codex command:

```bash
npx skills add blackblue-labs/skill2 -g -a codex -y
```

- Contributor CLI remains `uv run skill2 ...` under development section only.

- [ ] **Step 1: Write failing public-surface tests**

Add package tests that assert both READMEs:

- contain Claude marketplace commands;
- contain Codex npx command;
- describe six self-contained Skills;
- do not claim Skill2 is searchable in Codex `/plugins` yet;
- do not state user install includes helper CLI;
- keep English and Chinese commands byte-identical.

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH=src uv run python -m unittest tests.test_package
```

Expected: current clone/installer-first README fails assertions.

- [ ] **Step 3: Rewrite README install surface**

Order: Claude marketplace, Codex npx, manual fallback. Move top-level CLI commands to Contributor section. State `uv` is needed only when a Skill executes its deterministic script; no telemetry, hosted service, or PyPI install.

- [ ] **Step 4: Tighten manifests and package/publish rules**

Add author/homepage fields where supported. Keep version `0.1.0`. Update package/publish Skill rules: installed candidate contains scripts/runtime; publish smoke runs public installation plus one Skill-owned command.

- [ ] **Step 5: Verify GREEN**

```bash
PYTHONPATH=src uv run python -m unittest tests.test_package
jq empty .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json
claude plugin validate .
uv run skill2 package-check .
```

Expected: all commands exit 0; Claude validate has no schema errors.

- [ ] **Step 6: Regenerate runtimes, main review, commit**

```bash
PYTHONPATH=src uv run python tools/sync_skill_runtime.py
git add README.md README.zh.md .claude-plugin .codex-plugin src/skill2/package.py tests/test_package.py skills docs
git commit -m "document native install"
```

---

### Task 6: Prove three clean-install paths end to end

**Files:**
- Create: `tools/smoke_install.py`
- Create: `tests/test_smoke_install.py`
- Modify: `docs/CURRENT_STATUS.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- `tools/smoke_install.py --mode install-sh|npx|claude|all`.
- Each mode uses a fresh temporary HOME, records no secrets, removes/renames source checkout for detached execution, and exits nonzero on missing installed Skill or failed Skill-owned command.
- No tag, release, registry submission, or PyPI upload.

- [ ] **Step 1: Write failing smoke orchestration tests**

Unit-test command construction and detached checks with fake `npx`/`claude` executables. Assert no real HOME path appears in captured manifest/output.

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH=src uv run python -m unittest tests.test_smoke_install
```

Expected: module/file missing.

- [ ] **Step 3: Implement resumable smoke runner**

Write per-mode JSON checkpoints under `.skill2/install-smoke/<run-id>/`. Skip completed modes on `--resume`; failed mode never counts complete. Deduplicate by mode. Use local checkout as source for pre-release smoke.

- [ ] **Step 4: Verify unit tests GREEN**

```bash
PYTHONPATH=src uv run python -m unittest tests.test_smoke_install
uv run ruff check tools/smoke_install.py tests/test_smoke_install.py
```

- [ ] **Step 5: Run real clean-install smoke**

```bash
PYTHONPATH=src uv run python tools/smoke_install.py --mode install-sh
PYTHONPATH=src uv run python tools/smoke_install.py --mode npx
PYTHONPATH=src uv run python tools/smoke_install.py --mode claude
```

Acceptance:

- `install.sh`: six Skills copied; detached `skill2-create/scripts/run` creates a Skill.
- `npx`: six Skills discovered/installed; detached `skill2-visualize/scripts/run` renders terminal inventory.
- Claude: local marketplace validates and installs into temporary HOME; installed Skill-owned command runs after checkout path is unavailable.

- [ ] **Step 6: Run full completion gate**

```bash
PYTHONPATH=src uv run python -m unittest discover -s tests
uv run ruff check .
uv run skill2 lint skills
uv run skill2 package-check .
PYTHONPATH=src uv run python tools/sync_skill_runtime.py --check
git diff --check
```

Expected: all exit 0; six Skills lint clean; package issues 0; bundles current.

- [ ] **Step 7: Update status, main review, commit**

Record exact smoke evidence and remaining external condition: Codex curated marketplace listing not submitted. Do not call it available.

```bash
git add tools/smoke_install.py tests/test_smoke_install.py docs/CURRENT_STATUS.md CHANGELOG.md
git commit -m "verify native installs"
```

---

## Final Review

- [ ] Compare every requirement in `docs/superpowers/specs/2026-07-13-marketplace-first-install-design.md` against current files and fresh command output.
- [ ] Confirm user install paths do not install global Skill2 CLI.
- [ ] Confirm copied single Skill works without repository checkout.
- [ ] Confirm generated runtime is reproducible and stale changes fail package-check.
- [ ] Confirm no tag, GitHub Release, PyPI upload, or marketplace submission occurred.
- [ ] Push `main` only after full verification and final diff review.
