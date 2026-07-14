# Public Distribution

Use this phase only for public documentation or remote distribution work.

## README

`README.md` is the canonical English document.

Add a localized README when the user's query is primarily non-English or the user requests a language. Use `README.<language-code>.md`; Chinese uses `README.zh.md`. Preserve existing translations unless removal is requested. Do not require a Chinese README for English-only work.

When a translation exists:

- Link it from `README.md` and back to English.
- Keep install commands and factual claims equivalent.
- Translate prose; do not translate commands, paths, product names, or URLs.

Recommended order:

1. Identity and concrete value.
2. Common user questions or use cases.
3. Native install paths, then fallback paths.
4. Compact capability table.
5. Privacy, compatibility, and known limits.
6. Design, contributor, and license links.

Claim only shipped capabilities and available install paths. Never hardcode a Skill count; derive it from the repository.

## Preflight

Match checks to selected profiles:

- Native: lint, resolved resources, native install path, README and manifest consistency.
- Artifact: Native checks plus versioned artifact, checksum, and artifact install smoke.
- Release: relevant tests, clean intended diff, version and changelog when versioned, exact destinations, and public install plan.

Do not add artifact work to a native-only release. Do not require a build from a content-only repository.

## Remote Writes

Before push, tag, release, registry, or marketplace actions:

1. State exact destination and writes.
2. Treat an explicit user request for the named action as approval; ask only when destination or scope is ambiguous.
3. Execute once and report failures honestly.
4. Verify the public source and documented install path when feasible.

Do not claim a registry or marketplace listing before it exists.

## Output

Return selected profiles, README languages, checks run, remote writes, public URLs, install evidence, and blockers.

```bash
uv run --script <skill-dir>/scripts/run -- publish-check . --json
```
