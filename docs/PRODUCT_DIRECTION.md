# Product Direction

## Thesis

Skill2 is a skill pack first.

CLI exists to give those skills deterministic hands.

```text
Skill2 skills teach agents how to build, test, package, publish, and maintain skills.
Skill2 CLI provides scaffolding, lint, isolated test, usage extraction, and reports.
```

## Target User

People who already use Codex, Claude Code, OpenCode, Cursor, or similar coding agents and want reusable repo-local skills.

They need:

- how to write a good skill
- how to test whether it activates
- how to package it for other people
- how to avoid broken install paths
- how to see whether skills are used
- how to prune old skills

## Final Shape

```text
skill2/
  skills/
    skill2-build/
      SKILL.md
      references/
    skill2-test/
      SKILL.md
      references/
    skill2-package/
      SKILL.md
      references/
    skill2-audit/
      SKILL.md
      references/
    skill2-prune/
      SKILL.md
      references/

  src/skill2/
    cli.py
    scan.py
    lint.py
    test.py
    usage.py
    report.py
    scaffold.py

  docs/
```

## Skill Pack

### `skill2-build`

Use when user wants to create or improve a skill.

Agent duties:

- identify target workflow
- decide skill scope
- write compact `SKILL.md`
- add references/scripts only when needed
- generate scenario cases
- run `skill2 lint`

### `skill2-test`

Use when user asks if a skill works.

Agent duties:

- build isolated test cases
- run target skill alone
- check activation
- check non-activation
- check outcome assertions
- explain gaps

CLI support:

```bash
skill2 test ./skills/foo --agent codex --cases cases/foo.yaml --isolate
```

### `skill2-package`

Use when preparing skill repo for other people.

Agent duties:

- make installable layout
- check cross-harness compatibility
- write README install section
- add license
- add version/changelog
- produce marketplace/plugin metadata when applicable

CLI support:

```bash
skill2 scaffold skill-repo
skill2 lint --package
```

### `skill2-audit`

Use when reviewing a skill library.

Agent duties:

- scan all skills
- find long descriptions
- find broken references
- find overlap/conflicts
- find risky scripts
- produce issue list

CLI support:

```bash
skill2 scan ./skills --json
skill2 lint ./skills
```

### `skill2-prune`

Use when cleaning a skill library.

Agent duties:

- read usage report
- identify high/low/never-used skills
- propose keep/merge/downgrade/projectize/delete
- never delete without human approval

CLI support:

```bash
skill2 usage --codex ~/.codex --json
skill2 report --out report.html
skill2 suggest --repo .
```

## CLI Role

CLI is not the product surface. Skills are.

CLI should do only deterministic work:

- scaffold files
- validate schema
- count tokens
- scan references
- parse logs
- run isolated harness commands
- render static reports

Agent should do judgment:

- choose scope
- interpret results
- decide merge/delete
- rewrite skill text
- explain tradeoffs

## Install Story

### For users

Install skills into a repo:

```bash
npx skill2 init
```

or manual:

```bash
cp -R skills/skill2-* .agents/skills/
```

Optional CLI:

```bash
uv tool install skill2
```

### For agents

After install, user can say:

```text
帮我给这个 repo 写一个 skill
测试这个 skill 是否会触发
把这个 skill repo 做成别人好安装的开源仓库
看看我的 skill library 哪些该删
生成 skill 使用频率报告
```

Agent loads Skill2 skill, then calls CLI where useful.

## Open Source Packaging Standard

A good skill repo should include:

```text
README.md
LICENSE
CHANGELOG.md
install.sh
skills/
  skill-name/
    SKILL.md
    references/
    scripts/
    assets/
examples/
cases/
```

Checks:

- `SKILL.md` frontmatter valid
- `name` matches directory
- `description` short trigger text, not workflow summary
- references exist
- scripts executable where needed
- install copies skills to target harness paths
- README has install, usage, compatibility, privacy
- no secrets
- no machine-local absolute paths
- no huge unneeded assets

## Usage Visualization

Goal: show whether skill library matches real behavior.

Charts:

- calls by skill
- last used
- never used
- co-activation graph
- skill size vs usage
- activation gaps from tests
- false positives from negative tests
- maintenance actions over time

Report form:

- local static HTML first
- no server
- no hosted telemetry

## Isolated Testing

Core method:

```text
target skill + temp skill root + temp home + fresh session + scenario prompt
```

Test zones:

- core positive
- adjacent positive
- negative
- stress
- outcome assertions

Codex first:

- exact isolated `SKILL.md` read = activation candidate
- explicit event if runtime exposes one
- output assertions separate from activation

## Prior Art Takeaway

Tripwire already validates activation coverage via real agent sessions and prompt matrices.

Skill2 should not copy Tripwire as a CI-only linter.

Skill2 should combine:

- skill pack for agents
- CLI scaffolding
- isolated tests
- open-source packaging
- local usage analytics
- pruning dashboard

## MVP Reframed

MVP should ship these in order:

1. `skills/skill2-build`
2. `skills/skill2-test`
3. `skill2 scaffold skill`
4. `skill2 lint`
5. `skill2 test --agent codex --isolate`
6. `skill2 report` static HTML

Do not start with broad dashboard.

Start with one strong loop:

```text
agent writes skill -> CLI scaffolds/lints -> isolated test proves activation -> README explains install
```

## Decision

Repo should pivot from CLI-first to skills-first.

Current `.agents/skills/isolated-skill-test` should move to:

```text
skills/skill2-test/SKILL.md
```

Then add:

```text
skills/skill2-build/SKILL.md
skills/skill2-package/SKILL.md
skills/skill2-audit/SKILL.md
skills/skill2-prune/SKILL.md
```
