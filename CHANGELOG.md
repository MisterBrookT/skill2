# Changelog

## Unreleased

- Add `tools/smoke_install.py` clean-install smoke for `install.sh`, `npx skills add`, and Claude local marketplace; resumable checkpoints under `.skill2/install-smoke/`.

## 0.1.0 - 2026-07-13

- Six-skill library: create, test, package, publish, audit, visualize.
- Merge lifecycle review into `skill2-visualize`; retire standalone prune skill.
- Add scan/lint JSON and SARIF output.
- Add isolated Codex/Claude activation and outcome testing, baseline, JUnit, checkpoint/resume, early-stop.
- Add package/publish preflight and skill-repo scaffolding.
- Add local Codex usage adapter with activation/noise classification.
- Add conservative maintenance suggestions and terminal visualization.
- Add dry-run, conflict-gated, staged installer with provenance.
- Add bilingual README and terminal usage visualization.
