<p align="center">
  <img src="docs/readme-icon-v2.svg" width="88" alt="Skill2 icon">
</p>

<h1 align="center">Skill2</h1>

<p align="center">
  <strong>Skills for your skills.</strong><br>
  <strong>Full-lifecycle management for Agent Skill libraries.</strong>
</p>

<p align="center">
  Test and audit Agent Skills before shipping. Catch bad triggers, weak evidence, and packaging defects—locally.<br>
  Visualize usage and test status across your library, then surface evidence-backed cleanup candidates.
</p>

<p align="center"><a href="README.zh.md">中文</a></p>

<p align="center">
  <img alt="GitHub stars" src="https://img.shields.io/github/stars/blackblue-labs/skill2?style=flat-square">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-111111?style=flat-square">
  <img alt="Local first" src="https://img.shields.io/badge/data-local--only-111111?style=flat-square">
  <img alt="MIT license" src="https://img.shields.io/github/license/blackblue-labs/skill2?style=flat-square&color=111111">
</p>

<p align="center">
  <img src="docs/readme-hero.svg" alt="Skill2 terminal workflow">
</p>

## Why Skill2

Writing one Agent Skill is easy. Maintaining twenty is harder.

As your library grows, three questions matter:

- Does it trigger when it should—and stay quiet when it should not?
- Does it improve the outcome?
- Should it stay, be revised, or enter cleanup review?

Skill2 treats Agent Skills as testable, auditable software units. Five focused Skills help agents create, test, audit, package, and visualize a library—while deterministic scripts keep evidence reproducible and local.

## Install

### Claude Code

```text
/plugin marketplace add blackblue-labs/skill2
/plugin install skill2@skill2-marketplace
```

Installs five self-contained Skills.

### Codex

```bash
npx skills add blackblue-labs/skill2 -g -a codex -y
```

Copies the five self-contained Skills for Codex.

### Manual fallback

```bash
git clone https://github.com/blackblue-labs/skill2.git ~/.skill2 && ~/.skill2/install.sh
```

Copies Skills only (`install.sh` supports `--dry-run` and conflict-gated `--force` from a checkout). Requires Git. [uv](https://docs.astral.sh/uv/) is needed only when a Skill runs its deterministic script. Skill scripts use `uv run --script`; first run may fetch declared dependencies into the uv cache; offline use requires a warm cache. Data stays local; no hosted service, telemetry, or PyPI install for users.

## Five focused Skills

| Skill | Agent uses it when |
| --- | --- |
| `skill2-create` | Creating, updating, or restructuring a skill. |
| `skill2-test` | Testing activation and outcome in isolation. |
| `skill2-package` | Packaging, documenting, and optionally publishing a Skill repository. |
| `skill2-audit` | Finding contract, safety, and behavior gaps. |
| `skill2-visualize` | Viewing inventory, direct calls, zero-use candidates, test status, and conservative lifecycle review candidates. |

## Try it

Ask the agent directly:

```text
Create a project-level skill for this workflow.
Audit this skill library and show only evidence-backed findings.
Visualize which skills are called directly and which have zero direct calls.
```

## Local-first evidence

Skill2 visualizes skill inventory and usage from local agent session logs. Data stays on your machine; prompts and transcripts are never included.

## Design

Skills are the product; deterministic scripts support them. The repository dogfoods every rule it teaches. Package defaults to native distribution and adds artifact or release work only when requested. Visualize never changes a library.

| Area | Prior art | Adopted |
| --- | --- | --- |
| Skill format | [Agent Skills spec](https://agentskills.io/specification), [Anthropic Skills](https://github.com/anthropics/skills) | Portable `SKILL.md`, progressive disclosure, owned resources. |
| Authoring | [Superpowers](https://github.com/obra/superpowers), [writing-skills](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md) | Skills-first structure, trigger-first descriptions, dogfood. |
| Evaluation | [Superpowers evals](https://github.com/prime-radiant-inc/superpowers-evals), [Tripwire](https://github.com/bharath31/tripwire), [Waza](https://github.com/microsoft/waza), [skill-eval](https://github.com/fede0089/skill-eval), [agent-skills-eval](https://github.com/darkrishabh/agent-skills-eval), [skillci](https://github.com/tolztoy/skillci), [skill-distill](https://github.com/lov-alt/skill-distill) | Isolated runs, positive/negative routing, baseline, deterministic assertions. |
| Packaging | [agent-scripts](https://github.com/steipete/agent-scripts), [awesome-copilot](https://github.com/github/awesome-copilot), [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills), [superpowers-marketplace](https://github.com/obra/superpowers-marketplace), [Caveman](https://github.com/JuliusBrussee/caveman), [OpenAI Plugins](https://github.com/openai/plugins) | Idempotent installs, conflict gates, marketplace manifests, CI. |

Skill2 thanks these projects and their maintainers. Their work shaped this repository's architecture and design principles.

See [design](docs/DESIGN.md) and [prior art](docs/PRIOR_ART.md).

## Development

Contributor and CI use the checkout CLI. This is not a user install step:

```bash
uv sync
PYTHONPATH=src uv run python -m unittest discover -s tests
uv run ruff check .
uv run skill2 lint skills
uv run skill2 package-check .
```

MIT
