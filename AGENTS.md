# AGENTS.md

## Project

Skill2 = local governance tool for agent skill libraries.

Goal: lint skills, measure real usage, visualize hot/cold skills, suggest keep/merge/downgrade/projectize/delete.

## Current State

Docs-first repo. CLI not implemented.

Start with:

- `README.md`
- `docs/MVP.md`
- `docs/ARCHITECTURE.md`
- `docs/PRIOR_ART.md`

## First Implementation Target

Build Python CLI with `uv`.

Commands:

```bash
skill2 scan <skills_dir> --json
skill2 usage --codex ~/.codex --json
skill2 test <skill_dir> --agent codex --cases <cases.yaml> --isolate
skill2 report --scan scan.json --usage usage.json --out report.html
skill2 suggest --repo <repo>
```

## Constraints

- Local-first.
- No hosted telemetry.
- Do not upload transcripts.
- Treat usage events as approximate until confidence labels mature.
- Do not auto-delete skills.
- Isolated tests must not inherit user/global skills unless the case opts in.

## Test Fixture

Primary fixture:

```text
~/workspace/my-agent-config
```

Expected first reproduced decision:

```text
search-strategy + smart-fetch + internet-reach -> agent-search references
```

## Skill Test Protocol

Project skill:

```text
.agents/skills/isolated-skill-test/SKILL.md
```

Use it before implementing `skill2 test`.
