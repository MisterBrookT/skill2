---
name: skill2-visualize
description: "Use when viewing skill inventory/usage/test status, or reviewing delete/downgrade/merge/projectize candidates."
---

# Visualize Skill Libraries

Present local inventory, usage, and test evidence in the terminal. When review is useful, surface **delete** and **downgrade** candidates in plain language (plus optional merge/projectize). Never modify the library.

## Ownership

- Visualize presents evidence and optional read-only delete/downgrade candidates.
- Audit finds static defects.
- Test produces behavior evidence.
- Create applies approved merges, moves, or restructuring.

## Method

1. Run terminal `skill2 visualize` against the skill root, Codex + Claude usage roots, and test-run evidence.
2. Run read-only `skill2 suggest --json` against the same roots (visualize CLI also embeds a short candidate block).
3. Present a short terminal summary only (see Output). Keep observed facts separate from inference.
4. If delete/downgrade candidates were shown, end with the Output contract question (final line).
5. Read `references/lifecycle-suggestions.md` only when the user asks for detailed expansion of a candidate.
6. Never modify, delete, move, or merge skill files. No HTML or report-file flow.

## Interpretation

- Exact `SKILL.md` reads are usage evidence, not complete invocation history.
- Zero direct calls means current adapters found none; it does not prove no use.
- Broad scans, maintenance, and worker reads are not direct activation.
- Missing tests remain missing; never infer pass.
- Low frequency never authorizes deletion.
- **Delete candidate** ≠ delete now. It means: no usage, no tests, no owner signal — *maybe* removable after human check.
- **Downgrade candidate** ≠ bad skill. It means: mostly broad/worker noise; might be a piece of another skill, not a standalone.

## Output

Default terminal response: compact all-skill frequency chart. Target ≤ inventory skill count + 14 non-empty lines. Expand only after the user asks for detail.

Required default shape:

1. One summary line (inventory totals + key usage/test counts).
2. Compact all-skill terminal bar chart — exactly one row per skill in inventory (include zero-call skills). Sort by direct desc, then indirect desc, then name. Each row: skill name, stacked bar (`█` direct + `░` indirect), D/I counts. Include a short legend under the chart.
3. **Suggestions block** (plain words — do **not** say "lifecycle"):
   - **Delete candidates** — up to 5 (`delete_candidate`)
   - **Downgrade candidates** — up to 5 (`downgrade`)
   - Optional one-liners for merge/projectize only if present
   - If a bucket is empty, print `(none)` for that bucket
4. One evidence-limit line.
5. Final yes/no detailed-review question only when at least one delete or downgrade candidate was shown.

Do not print by default:

- the word "lifecycle" (too abstract for users)
- boxed tables (no box-drawing borders)
- full keep tables
- separate full zero-call list (zeros belong in the all-skill chart)
- repeated facts already shown above
- full evidence methodology / interpretation essay

Hard contract — when any delete or downgrade candidates are shown:

- Final line of the reply must be a direct yes/no question about those candidates.
- Required intent (match user language): ask if they want a detailed review.
- English form must include `want a detailed` or `detailed review`.
- If the user is writing in another language, mirror that language for the question only; skill body stays English.
- Do not auto-apply delete/downgrade/merge actions.

```bash
skill2 visualize --skills skills --codex ~/.codex --claude ~/.claude
skill2 visualize --skills skills --codex ~/.codex --claude ~/.claude --json
skill2 suggest --skills skills --codex ~/.codex --claude ~/.claude --tests .skill2/test-runs --json
```
