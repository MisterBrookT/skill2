<p align="center">
  <img src="docs/readme-icon.svg" width="96" alt="Skill2 icon">
</p>

<h1 align="center">Skill2</h1>

<p align="center">
  Skills for your skills.
</p>

<p align="center">
  A skill pack plus optional CLI for building, testing, packaging, auditing, and pruning agent skills inside your own repos.
</p>

<p align="center">
  <a href="README.zh.md">中文</a>
</p>

<p align="center">
  <img alt="GitHub stars" src="https://img.shields.io/github/stars/MisterBrookT/skill2?style=flat-square">
  <img alt="License" src="https://img.shields.io/github/license/MisterBrookT/skill2?style=flat-square">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-1f2933?style=flat-square">
  <img alt="Local first" src="https://img.shields.io/badge/local--first-no%20telemetry-2dd4bf?style=flat-square">
</p>

<p align="center">
  <img src="docs/readme-hero.svg" alt="Skill2 manages agent skills">
</p>

## Why

Agent skills are becoming package-like. A repo can now carry reusable instructions, references, scripts, and tests that teach an agent how to work in that repo.

Skill2 gives that layer its own maintenance loop: create skills, test whether they activate, package them for other people, audit the library, and prune what no longer earns its place.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/MisterBrookT/skill2/main/install.sh | bash -s -- codex
```

This installs the Skill2 skill pack into `~/.agents/skills`. No telemetry. No hosted service.

## Skill Pack

| Skill | Use it for |
| --- | --- |
| `skill2-build` | Create or improve a skill. |
| `skill2-test` | Isolated activation and outcome testing. |
| `skill2-package` | Make a skill repo installable. |
| `skill2-audit` | Scan a skill library for structure and safety issues. |
| `skill2-prune` | Suggest keep, merge, downgrade, projectize, or delete. |

## CLI

The CLI is a deterministic helper used by the skills.

Implemented:

```bash
skill2 scaffold skill my-skill --description "Use when ..."
skill2 lint skills
skill2 scan skills --json
```

Planned:

```bash
skill2 test ./skills/my-skill --agent codex --cases cases/my-skill.yaml --isolate
skill2 usage --codex ~/.codex --json
skill2 report --out report.html
skill2 suggest --repo .
```

## Local Checks

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m skill2.cli lint skills
```

## Docs

- [Product direction](docs/PRODUCT_DIRECTION.md)
- [MVP](docs/MVP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Isolated testing](docs/ISOLATED_TESTING.md)
- [Prior art](docs/PRIOR_ART.md)
- [Popular skill repo references](docs/SKILL_REPO_REFERENCES.md)

## Status

Early. Skill pack exists. CLI supports scaffold and lint. Isolated runtime tests, usage parsing, and dashboard reports are next.

## License

MIT
