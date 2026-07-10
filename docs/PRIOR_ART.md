# 先例调研

更新：2026-07-10。

Superpowers 复核基线：[v6.1.1](https://github.com/obra/superpowers/releases/tag/v6.1.1)，提交 [`d884ae0`](https://github.com/obra/superpowers/commit/d884ae04edebef577e82ff7c4e143debd0bbec99)。

## 结论

现有项目已覆盖格式、路由评测、真实 agent 测试、CI、安装。

Skill2 缺口定位：

```text
skill files + isolated tests + local usage
  → quality/lifecycle evidence
  → human-reviewed maintenance actions
```

不再做另一个通用 linter。

## 规范来源

| 来源 | 证据 | Skill2 采用 |
| --- | --- | --- |
| [Agent Skills spec](https://agentskills.io/specification) | 标准目录、frontmatter、progressive disclosure | 核心兼容契约 |
| [Codex skills](https://developers.openai.com/codex/skills/) | Codex discovery、`agents/openai.yaml`、依赖声明 | Codex adapter |
| [Anthropic skills](https://github.com/anthropics/skills) | 公开 skill 包与资源组织 | 资源随 skill 分发 |
| [Superpowers](https://github.com/obra/superpowers) | skills-first、多 harness、测试、打包 | Build 方法与仓库结构 |
| [writing-skills](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md) | `description=WHEN`、RED/GREEN/REFACTOR | skill 行为迭代 |
| [Superpowers evals](https://github.com/prime-radiant-inc/superpowers-evals) | 真实 CLI、场景与后检 | live eval 参考 |

## 测试工具

| 项目 | 已有能力 | Skill2 学什么 | 不照搬 |
| --- | --- | --- | --- |
| [Tripwire](https://github.com/bharath31/tripwire) | lint、激活覆盖、正反例、CI、drift | activation/outcome 分离；固定 scenarios | Codex 路径读取只是启发式；隔离不足 |
| [Waza](https://github.com/microsoft/waza) | 正负 trigger、多 grader、多 trial、模型矩阵 | repetitions、grader 分层 | 首版不做模型矩阵 |
| [skill-eval](https://github.com/fede0089/skill-eval) | worktree、真实 dispatch、baseline、pass@k | 强隔离与对照组 | 首版只做 Codex |
| [agent-skills-eval](https://github.com/darkrishabh/agent-skills-eval) | with/without、标准产物 | baseline 与 artifact shape | system 注入不等于自然 activation |
| [skillci](https://github.com/tolztoy/skillci) | lint、安全审计、fixtures、确定性断言 | Outcome assertions、工具白名单 | 不把强制注入当 activation 测试 |
| [skill-distill](https://github.com/lov-alt/skill-distill) | description lint、重叠、路由 benchmark | confusion/overlap 预检 | 静态相似度不能代替真实运行 |

## 分发与治理

| 项目 | 已有能力 | Skill2 学什么 |
| --- | --- | --- |
| [agent-scripts](https://github.com/steipete/agent-scripts) | symlink、路径适配、冲突处理 | adapter 分层、幂等同步；不复制个人目录假设 |
| [awesome-copilot](https://github.com/github/awesome-copilot) | schema、PR gate、夜间扫描 | CI 分层、固定 Action SHA |
| [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 大型库、references/scripts、CI scan | 大库扫描、安全检查 |
| [superpowers-marketplace](https://github.com/obra/superpowers-marketplace) | 薄 marketplace manifest | registry 与 skill 内容分离；Skill2 暂不做 registry |

## 抽象规范

### 内容

- 扁平 `skills/<name>/SKILL.md`。
- `name` 与目录一致。
- `description` 只负责触发。
- references/scripts/assets 按需加载。
- 核心内容跨 harness；适配文件独立。

### 行为

- Activation 与 Outcome 分测。
- 正例、邻近正例、反例、改写、压力场景。
- 无 skill baseline；多 trial。
- 结构化事件与确定性断言优先。
- 原始 transcript/artifacts 可审计。

### 分发

- 安装前 preview。
- 记录 source、ref、tree SHA。
- 原子、幂等、冲突可见。
- 第三方脚本不自动执行。
- workspace trust 不等于工具授权。

### 生命周期

- usage 事件必须有 source/confidence。
- 维护读取与真实调用分开。
- low usage 不能单独触发删除建议。
- destructive action 始终人工确认。

## Skill2 差异

- Skills-first，不是 CLI-first。
- Codex-first 强隔离。
- 测试结果与本地真实 usage 联合分析。
- 从质量检查延伸到 merge/downgrade/projectize/prune。
- 无云端 telemetry。

## 搜索边界

本轮检查 GitHub 仓库与官方规范。Reddit、X、小红书不作为实现规范来源；未纳入结论。

每个 Skill 的具体设计映射见 [SKILL_DESIGN.md](SKILL_DESIGN.md)。
