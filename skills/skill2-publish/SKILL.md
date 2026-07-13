---
name: skill2-publish
description: "Use when publishing a skill repository, README, release, registry entry, or public install verification."
---

# Publish Skill Repositories

Make a verified package discoverable, understandable, and installable by strangers.

## Ownership

- Publish owns public presentation, release metadata, remote actions, and public reinstall verification.
- Package owns candidate construction and local installability.
- Do not rebuild package internals during release work; return blockers to Package.

## Public Surface

- State product identity and concrete value before implementation detail.
- Show one primary installation path.
- List only shipped capabilities and supported environments.
- State privacy, compatibility, and known limits.
- Keep translated README installation commands equivalent.
- Keep README, manifests, installer, changelog, and release version consistent.

## Preflight

Require clean package check, tests, CI state, working tree, version, changelog, artifacts, checksums, destinations, and public install plan.

## Remote Gate

Tag, push, release, registry, and marketplace actions require:

1. Exact dry-run.
2. Explicit user confirmation.
3. One controlled execution.
4. Honest failure reporting.
5. Reinstall from public source and verify installed version.

## Output

Return preflight result, planned remote writes, approval state, published URLs, and public reinstall evidence.

```bash
uv run --script <skill-dir>/scripts/run -- publish-check . --json
```
