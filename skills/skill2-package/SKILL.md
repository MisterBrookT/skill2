---
name: skill2-package
description: "Use when making a skill repository installable, adding manifests or installers, building artifacts, or checking package compatibility."
---

# Package Skill Repositories

Produce a reviewable, reproducible install candidate without remote writes.

## Ownership

- Package owns repository shape, required manifests, installer, artifact, checksum, and clean-install smoke test.
- Publish owns public README, repository metadata, tag, release, registry, and marketplace actions.
- Never tag, push, release, or upload.

## Candidate

Keep shared behavior in `skills/<name>/SKILL.md`. Add harness metadata only when a target format requires it. Include only resources used by installed skills.

## Gates

- Every Skill passes format and repository lint.
- References, scripts, and assets resolve.
- Scripts are auditable and executable when required.
- Installer is explicit, repeatable, conflict-aware, and safe to preview.
- Candidate contains no secrets, accidental local paths, or unrelated large files.
- Clean temporary installation succeeds.
- Version and checksum identify exact artifact.
- README installation command, when present, targets candidate.

## Output

Return candidate path, version, checksum, install-smoke result, and unresolved blockers. Hand candidate to Publish.

```bash
uv run --script <skill-dir>/scripts/run -- scaffold skill-repo <name>
uv run --script <skill-dir>/scripts/run -- lint skills
uv run --script <skill-dir>/scripts/run -- package-check . --json
```
