# Isolated Skill Testing

## Question

Does a skill work because it is good, or because current session/global context helped it?

Skill2 answer: run the skill alone.

## What To Test

Three layers:

1. activation: correct prompts load the skill.
2. non-activation: unrelated prompts do not load it.
3. outcome: once loaded, output satisfies assertions or rubric.

## Case File

```yaml
skill: agent-search
agent: codex
cases:
  - name: core prior-art request
    prompt: "research prior art for testing agent skills"
    expect_activation: agent-search
    assertions:
      - type: contains
        value: "prior art"

  - name: unrelated code edit
    prompt: "rename variable foo to bar in app.py"
    expect_not_activation:
      - agent-search

  - name: blocked page fetch
    prompt: "read this JS-heavy page and summarize it"
    expect_activation: agent-search
```

## Isolation Contract

Default `--isolate`:

- temp home
- temp `.agents/skills` with only target skill
- minimal `AGENTS.md`
- empty worktree unless fixture passed
- no inherited chat history
- no unrelated user skills
- no project memories
- allowlisted tools only

Fixture mode:

```bash
skill2 test ./skills/agent-search \
  --agent codex \
  --cases cases/agent-search.yaml \
  --fixture fixtures/search-task \
  --isolate
```

## Codex Detection

Ideal signal: explicit skill activation event.

Current practical signal:

- exact read of isolated path: `.../.agents/skills/<name>/SKILL.md`
- plus transcript output and tool calls

Confidence:

| Signal | Confidence |
| --- | --- |
| explicit activation event | high |
| exact isolated `SKILL.md` read | medium |
| only text mentions skill name | low |
| no event but output follows skill | inconclusive |

## Result Labels

- `activation_pass`: expected skill loaded.
- `activation_gap`: expected skill did not load.
- `false_positive`: forbidden skill loaded.
- `outcome_pass`: output assertions passed.
- `outcome_fail`: skill loaded but output failed.
- `inconclusive`: harness lacks signal.

## Prior Art

[Tripwire](https://github.com/bharath31/tripwire) is closest: lint + prompt matrix + real agent sessions + activation coverage + CI reruns. It also separates activation from outcome evals.

[skillci](https://github.com/tolztoy/skillci) covers scenario-test framing.

Skill2 difference:

- Codex-first local isolation.
- Usage analytics and pruning dashboard.
- Same cases feed both CI and lifecycle suggestions.
