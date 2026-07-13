# Delete / Downgrade Suggestions (detail)

Read only when Visualize surfaces delete or downgrade candidates that need interpretation.

Avoid the word "lifecycle" when talking to users. Prefer:

- **Delete candidates**
- **Downgrade candidates**

## Actions (plain language)

| Action | User-facing label | Signal |
| --- | --- | --- |
| Keep | keep | Independent value, clear trigger, or strong use/test evidence |
| Merge | merge | Overlapping triggers, repeated co-use, shared ownership |
| Downgrade | Downgrade candidates | Looks like a component of another skill; mostly broad/worker reads, not direct use |
| Projectize | projectize | Explicit project ownership or value confined to one repository |
| Delete candidate | Delete candidates | No use, no tests, no owner/dependency signal — candidate only |

## Evidence

Use read-only `skill2 suggest --json` as the deterministic candidate source. Prefer observed facts from:

- Inventory and ownership from scan
- Usage events with source and confidence
- Existing test-run summaries

Separate direct activation from broad scan, maintenance write, and worker read. Only direct activation is close to real invocation.

If CLI or evidence is unavailable or fails: lower confidence or mark `inconclusive`. Do not invent usage or test results.

## Confidence and Counterarguments

For every recommendation include:

- **Evidence** — observed facts only
- **Confidence** — high / medium / low / inconclusive
- **Counterargument** — strongest reason the recommendation may be wrong
- **Reversible next step** — smallest check or change that can be undone

Do not present inference as fact. Example: "0 direct calls in current adapters" is a fact; "safe to delete" is inference.

## Hard Rules

- **Low frequency alone never authorizes removal.**
- High-value rare Skills may remain when tests or critical workflows support them.
- Delete is a candidate, not an action.
- Downgrade is a structure hint, not a quality insult.
- Never modify, delete, move, or merge skill files from this workflow.
- Require user approval before any apply step (Create or ordinary edit flow).
