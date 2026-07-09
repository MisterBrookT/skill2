# Architecture

## Shape

```text
skill2
  scan      read skill files
  usage     read local logs / hook events
  test      run isolated skill scenarios
  report    build dashboard
  suggest   produce maintenance actions
```

## Data Model

```json
{
  "skill": {
    "name": "agent-search",
    "path": "/repo/skills/agent-search/SKILL.md",
    "description": "Search/read router",
    "body_tokens": 1200,
    "references": ["references/search-strategy.md"],
    "scripts": ["scripts/internet-reach-doctor.sh"],
    "scope": "global"
  }
}
```

```json
{
  "activation": {
    "timestamp": "2026-07-09T21:00:00Z",
    "harness": "codex",
    "session": "rollout-...",
    "skill": "agent-search",
    "source": "log-path-match",
    "confidence": 0.45
  }
}
```

```json
{
  "test_case": {
    "name": "core trigger",
    "prompt": "research prior art for agent skill testing",
    "expect_activation": "agent-search",
    "expect_not_activation": [],
    "assertions": [{"type": "contains", "value": "prior art"}]
  }
}
```

```json
{
  "suggestion": {
    "action": "downgrade_to_reference",
    "target": "smart-fetch",
    "parent": "agent-search",
    "reason": "component skill mostly used through parent search router",
    "evidence": ["low direct usage", "parent references it"]
  }
}
```

## Pipeline

1. Parse skill tree.
2. Parse usage events.
3. Run isolated scenarios when requested.
4. Join by normalized skill name and canonical path.
5. Compute metrics.
6. Run suggestion rules.
7. Render HTML + JSON.

## Event Confidence

Use conservative labels.

| Signal | Confidence |
| --- | --- |
| explicit skill invocation event | high |
| system skill list only | ignore |
| `Read` tool on exact hub `SKILL.md` | medium |
| path string appears in old transcript | low |
| edit to skill file | maintenance, not activation |

## Hook Route

Logs may be incomplete. Add optional hook recorder:

```json
{"ts":"...","harness":"codex","event":"skill_read","skill":"agent-search","path":"..."}
```

Store locally:

```text
~/.skill2/events.jsonl
```

No network. No hosted telemetry.

## Test Runner

`skill2 test` creates an isolated harness home:

```text
tmp/
  home/
    .codex/
      AGENTS.md
    .agents/
      skills/
        target-skill/
          SKILL.md
  work/
```

Codex first detection:

- high confidence if runtime exposes explicit skill event.
- current fallback: read of exact `skills/<name>/SKILL.md` path.
- output assertions run separately from activation detection.

Test result labels:

- `activation_pass`
- `activation_gap`
- `false_positive`
- `outcome_pass`
- `outcome_fail`
- `inconclusive`
