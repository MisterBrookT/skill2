# Skill2

Skills for your skills.

Skill2 is a local toolkit for maintaining agent skill libraries: lint the files, measure real usage, visualize hot and cold skills, and suggest what to keep, merge, downgrade, or delete.

[中文](README.zh.md)

## Status

Design repo. CLI not shipped yet.

## Why

Agent skills are becoming package-like. They need the same maintenance loop as code:

- lint: broken frontmatter, long descriptions, missing references, unsafe scripts
- coverage: which skills actually trigger
- analytics: high-frequency, low-frequency, never-used, co-activated skills
- pruning: delete, merge, downgrade to reference, or move to project-level scope

Most existing tools stop at validation. Skill2 aims at library governance.

## Planned CLI

```bash
skill2 scan ~/workspace/my-agent-config/skills --json > skill2-scan.json
skill2 usage --codex ~/.codex --claude ~/.claude --opencode ~/.config/opencode --json > skill2-usage.json
skill2 test ./skills/agent-search --agent codex --cases cases/agent-search.yaml --isolate
skill2 report --scan skill2-scan.json --usage skill2-usage.json --out report.html
skill2 suggest --repo ~/workspace/my-agent-config
```

## Core Ideas

| Layer | Output |
| --- | --- |
| Scan | structure issues, token size, references, scripts, duplicate descriptions |
| Usage | skill activation candidates from local harness logs or hooks |
| Test | isolated scenario runs: should activate, should not activate, should satisfy assertions |
| Quality | routing tests, confusion matrix, Hit@1/Hit@5 |
| Report | dashboard for hot/cold/unused skills and risk flags |
| Suggest | keep, merge, downgrade, projectize, delete |

## First Target

Reproduce one real maintenance decision:

`search-strategy`, `smart-fetch`, and `internet-reach` should be downgraded from top-level skills into `agent-search/references/`.

## Docs

- [MVP](docs/MVP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Isolated testing](docs/ISOLATED_TESTING.md)
- [Prior art](docs/PRIOR_ART.md)

## License

MIT
