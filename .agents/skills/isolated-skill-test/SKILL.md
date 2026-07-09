---
name: isolated-skill-test
description: "Use when designing or implementing Skill2 isolated tests for agent skills."
---

# Isolated Skill Test

Goal: test one skill without hidden help from current session, global rules, or neighboring skills.

## Protocol

1. Copy target skill into temp skill root.
2. Create temp home with minimal agent config.
3. Run one scenario per fresh session.
4. Detect activation.
5. Run output assertions.
6. Emit JSON result.

## Case Zones

- core positive: should activate
- adjacent positive: should activate
- negative: should not activate
- outcome: should satisfy assertions/rubric

## Codex First

Default detection:

- exact read of isolated `skills/<name>/SKILL.md` = medium confidence activation.
- explicit activation event = high confidence if available.
- text-only mention = low confidence.

## Hard Rules

- no inherited chat history.
- no unrelated skills.
- no user memory unless case opts in.
- no auto-delete based on test result.
- inconclusive is valid.

## Docs

Read:

- `docs/ISOLATED_TESTING.md`
- `docs/ARCHITECTURE.md`
- `docs/MVP.md`
