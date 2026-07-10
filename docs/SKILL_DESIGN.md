# Skill2 Skill 设计依据

目的：说明每个 Skill 为什么存在、借鉴什么、没有借鉴什么。来源不等于复制代码。

## 分层

| 层 | 来源 | 用途 |
| --- | --- | --- |
| 格式 | Agent Skills spec / `skills-ref` | `SKILL.md`、frontmatter、目录、渐进加载 |
| 方法 | Superpowers | Skill 是行为代码；scope、触发、case、baseline |
| 产品 | Skill2 | 管理 Skill Library 的生命周期、local-first usage、可视化、人类决策 |

## `skill2-build`

### 要解决什么

用户想让 Agent 学会一个新工作流时，先判断值不值得做 Skill，再决定：顶层 Skill、reference、项目级规则，或不做。然后才写最小可维护 Skill。

它不负责：隔离评测、公开发布、审计、清理。这些分别交给 `skill2-test`、`skill2-publish`、`skill2-audit`、`skill2-prune`。

### 设计映射

| 当前规则 | 来源 | Skill2 采用方式 |
| --- | --- | --- |
| 先判 scope，再写内容 | Superpowers `writing-skills`：一次性方案、项目私有约定不应变成通用 Skill | `顶层 / reference / 项目级 / 不做` 四选一 |
| `description` 写触发，不写流程 | Superpowers Skill Discovery Optimization | description 只回答“何时读”；流程留在正文 |
| 平铺 `skills/<name>/SKILL.md` | Agent Skills spec；Superpowers flat namespace | 一个 discoverable `SKILL.md`；不嵌套子 Skill |
| 细节进 `references/`，确定性操作进 `scripts/` | Agent Skills progressive disclosure；Superpowers supporting files | 默认单文件；重参考或复用工具才拆 |
| 每个新 Skill 带 case | Superpowers：把 Skill 当行为代码，先看 baseline 再写规则 | Build 输出正例、邻近反例、无关反例、outcome 断言 |
| 结构与安全检查 | Agent Skills spec + `skills-ref`；Skill2 policy | `skill2 lint` 做格式、断链、secret、脚本检查 |

### 当前结构如何实现

```text
用户请求
  → scope：Skill / reference / project / 不做
  → 最小 SKILL.md
  → 需要时加 references 或 scripts
  → cases/<name>.yaml
  → lint
  → 1 次隔离 dogfood + 人工审阅
```

对应 [skill2-build](../skills/skill2-build/SKILL.md)。

### 没有照搬什么

- 不照搬 Superpowers 的长篇 pressure/rationalization tables。
- 不强制完整 RED/GREEN/REFACTOR；当前是 1 trial + 人工验收。
- 不把所有工作流都做成 Skill；机械约束优先交给 lint/script。
- 不做跨所有 harness 的行为矩阵；0.1 先验证 Codex。

这不是缺失，而是产品取舍。Skill2 的目标是轻量 Skill Library 管理，不是复刻 Superpowers。

### 当前 dogfood 结论

首个 `build-core` A/B：`skill2-build` 触发正确；baseline 也完成输出。因此不能宣称增益。见 [原始样本](../cases/dogfood/skill2-build/build-core/README.md)。

下一步：把 build case 改成会暴露 scope/边界错误的真实 artifact 任务；用户审阅两边生成的文件，而非长文本回答。

## 后续 Skill 模板

每新增/改写一个 Skill，在本页补：

1. 用户问题与非目标。
2. 采用来源与具体映射。
3. 不采用内容与原因。
4. 自动 case。
5. 人工 dogfood 结论。

## 来源

- [Agent Skills specification](https://agentskills.io/specification)
- [Agent Skills reference validator](https://pypi.org/project/skills-ref/)
- [Superpowers: writing-skills](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md)
- [Superpowers repository](https://github.com/obra/superpowers)
