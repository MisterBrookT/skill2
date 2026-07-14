# Changelog

## 0.1.1 - 2026-07-14

- Merge publish into `skill2-package` as an optional release phase; ship five top-level Skills.
- Default to native distribution; require artifacts and checksums only when requested or required by a destination.
- Keep `README.md` as canonical English; add localized READMEs according to the user's query language.

## 0.1.0 - 2026-07-14

- Six-skill library: create, test, package, publish, audit, visualize.
- Ship six self-contained Skills with generated `scripts/run` + `_runtime/` bundles and package hash gate (`P2RT001`).
- Support Claude marketplace, Codex `npx skills add`, and manual Skills-only installation.
- Add resumable clean-install smoke for all three public installation paths.
- Add Codex plugin metadata, privacy/terms pages, and Linux CI coverage.
- Merge lifecycle review into `skill2-visualize`; retire standalone prune skill.
- Add scan/lint JSON and SARIF output.
- Add isolated Codex/Claude activation and outcome testing, baseline, JUnit, checkpoint/resume, early-stop.
- Add package/publish preflight and skill-repo scaffolding.
- Add local Codex usage adapter with activation/noise classification.
- Add conservative maintenance suggestions and terminal visualization.
- Add dry-run, conflict-gated, staged installer with provenance.
- Add bilingual README and terminal usage visualization.
