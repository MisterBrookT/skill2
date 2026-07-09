# Prior Art

## Summary

Existing tools cover lint, CI, install, registry, and activation tests.

Open gap: local usage telemetry, pruning dashboard, lifecycle suggestions.

## Tools

| Project | Focus | What to learn | Gap |
| --- | --- | --- | --- |
| [agent-skills-lint](https://github.com/swarmclawai/agent-skills-lint) | cross-agent validation, install, index | multi-harness flavors, JSON output | no usage analytics |
| [tripwire](https://github.com/bharath31/tripwire) | lint, activation coverage, CI, outcome evals | prompt matrix, real agent sessions, positive/negative zones | release gate, not daily usage governance |
| [skillci](https://github.com/tolztoy/skillci) | lint, security audit, scenario tests | skills as tested artifacts | no library lifecycle |
| [skill-distill](https://github.com/lov-alt/skill-distill) | description lint, diff, benchmark | routing accuracy, confusion matrix | no log-driven frequency analysis |
| [skillcheck](https://github.com/Jetty0728/skillcheck) | format, safety, token estimate | token cost, dangerous command scan | early small tool |
| [skillhub](https://github.com/Hayatelin/skillhub) | package manager | search, scaffold, install | distribution, not maintenance |
| [awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | directory | ecosystem map | not a maintenance tool |
| [Langfuse prompt improvement](https://langfuse.com/blog/2026-02-16-prompt-improvement-claude-skills) | trace feedback to prompt improvement | feedback loop | prompt observability, not skill routing |
| [Pendo Agent Analytics](https://support.pendo.io/hc/en-us/articles/41915386166683-Analyze-and-track-use-cases-for-your-AI-agents) | conversation/use-case analytics | clustering usage | SaaS product analytics, not local skill libraries |
| [OpenAI Codex Agent Skills](https://developers.openai.com/codex/skills) | official skill shape | instructions/resources/scripts contract | platform docs, not governance |

## Positioning

Do not compete as another linter.

Build missing layer:

```text
skill files + isolated scenario tests + local harness logs -> quality metrics -> pruning report -> human action
```

## Isolation Takeaway

Tripwire already proves activation coverage is testable: generate scenarios, run real agent sessions, detect which skill fires, commit scenarios, rerun in CI.

Skill2 should extend this:

- local-first Codex isolation
- one-skill-only temp skill root
- no global user rules unless explicitly requested
- usage analytics joined with test results
- pruning suggestions grounded in both observed usage and scenario coverage
