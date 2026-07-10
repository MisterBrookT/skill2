# Skill2 路线图

## 定位

Skill2 是 **agent skill 工程系统**。

```text
Skill2 skills：教 agent 设计、测试、打包、审计、清理 skills。
Skill2 CLI：提供可复现的扫描、隔离运行、日志解析、报告生成。
本地证据：连接 build → test → package → observe → prune。
```

用户安装的是一组 skills。CLI 是 skills 调用的确定性执行层，不是主要产品界面。

Skill2 不做：

- skill 目录或中心 registry
- 托管 observability / telemetry SaaS
- 只检查 Markdown 格式的 linter
- 未经确认自动删除或改写 skill
- 首版同时支持所有 agent harness 的完整行为测试

## 核心判断

好 skill 不能只靠格式定义。需要四层证据：

| 层 | 回答问题 | 输出 |
| --- | --- | --- |
| Contract | 能否被 harness 正确发现 | schema / path / link issues |
| Craft | 写法是否利于触发和维护 | lint advice |
| Behavior | 是否该触发时触发，触发后有效 | activation / outcome results |
| Lifecycle | 是否值得继续保留 | usage / report / suggestions |

规则必须标注来源：

- `ERROR`：官方格式或确定性运行错误。
- `WARN`：安全、可移植性、安装风险。
- `ADVICE`：Superpowers 等社区实践，不伪装成官方标准。
- `INSIGHT`：usage/test 推导出的维护建议。

## 学到的规范

### Build

来自 Agent Skills spec、Superpowers、本地 `authoring-skills`：

- `skills/<name>/SKILL.md` 是单一内容源。
- `description` 写触发条件，不写工作流摘要。
- 正文短；重参考进 `references/`；确定性动作进 `scripts/`。
- 先判断应该是顶层 skill、reference、项目级 skill，还是不该做 skill。
- skill 改动按行为迭代：无 skill 基线 → 最小 skill → 压力场景 → 修订。
- 官方契约、跨 harness 约束、作者偏好分层检查。

### Test

来自 Superpowers、Tripwire、Waza、skill-eval：

- Activation 与 Outcome 分开。
- 每个 case 新会话；只安装目标 skill；隔离用户配置和历史。
- 正例、邻近正例、反例、改写、压力场景都要覆盖。
- 支持 `with_skill` / `without_skill` 对照组。
- 结构化事件优先；读取目标 `SKILL.md` 只算中等置信度。
- 确定性断言优先；LLM judge 只评语义质量。
- 保存原始 transcript、工具事件、文件 diff、计时、模型与 skill hash。

### Package

来自 Agent Skills spec、Codex、agent-scripts、awesome-copilot：

- 通用 skill 内容与 harness adapter 分开。
- 安装目标路径不是源码目录。
- 安装前 preview；记录来源、ref、tree SHA。
- 原子安装；冲突检测；重复执行结果稳定。
- 不把 `allowed-tools` 当用户授权。
- 不默认执行第三方 skill 内脚本。

### Observe / Prune

Skill2 自己补的层：

- usage 不是“日志里出现过 skill 名”。
- 区分真实调用、维护编辑、全库扫描、worker 读取、低置信度文本命中。
- 低频不等于无用；结合最近使用、owner、测试、共现、项目边界。
- 所有合并、降级、项目化、删除建议都附证据。
- 建议只读；人确认后才改。

## 目标工作流

```text
skill2-build
  scope → baseline → scaffold/edit → lint → cases → test

skill2-test
  isolate → activate → assert outcome → compare baseline → record evidence

skill2-package
  validate → preview → adapter metadata → install smoke test

skill2-audit
  scan → lint → security → behavior gaps → report

skill2-prune
  usage + tests + ownership → keep/merge/downgrade/projectize/delete suggestions
```

## CLI 目标

```bash
skill2 scaffold skill <name>
skill2 scaffold skill-repo <name>

skill2 scan <path> --json
skill2 lint <path> --format text|json|sarif
skill2 package-check <repo> --json

skill2 test <skill> --agent codex --cases <file> --isolate \
  --trials 3 --baseline

skill2 usage --codex <codex-root> --json
skill2 report --repo <repo> --out report.html
skill2 suggest --repo <repo> --json
```

CLI 产物默认写入 `.skill2/`：

```text
.skill2/
  inventory.json
  test-runs/<run-id>/
  usage/events.jsonl
  suggestions.json
  report.html
```

所有 JSON 带 `schema_version`。原始证据与派生结论分开。

## 实施阶段

### M0：数据契约与真实 scan

目标：建立后续模块共用的稳定输入。

- 定义 `SkillRecord`、`Issue`、`Case`、`TestRun`、`ActivationEvent`、`Suggestion`。
- `scan` 输出 name、description、token estimate、resources、scripts、scope、hash。
- `lint` 消费 scan 结果，不再和 `scan` 混为同一命令。
- 正确解析 YAML frontmatter、Markdown links、资源路径。
- 增加 schema fixtures、CLI snapshot、GitHub Actions。
- 修正文档与实现不一致。

验收：当前 repo 与 `my-agent-config` 均可稳定扫描；JSON 可重复；CI 通过。

### M1：Build + Codex 隔离测试闭环

目标：证明 skill 自身有效。

- 扩展 case schema：`kind`、`control`、`variants`、`repetitions`、assertions。
- Codex runner：临时 `HOME/CODEX_HOME`、单一 skill root、空 worktree/fixture。
- 每 case 新会话；记录命令、版本、模型、skill hash、transcript。
- Activation：结构化事件优先，精确路径读取 fallback。
- Outcome：contains、regex、file exists/content、exit code、tool evidence。
- 支持无 skill baseline、3 trials、JSON/JUnit 输出。
- `skill2-build` 强制生成 case；用 Skill2 测 Skill2 自己。

验收：`cases/skill2-test.yaml` 在隔离环境跑通正例、反例、baseline；失败可解释、可复现。

### M2：Package + Audit

目标：让 skill repo 可安装、可审查。

- `scaffold skill-repo`。
- `package-check`：spec、断链、权限、secret、危险脚本、manifest、README/install。
- Codex adapter；Claude/OpenCode 只做路径与 metadata 兼容检查。
- install preview、冲突检测、来源/ref/tree SHA 记录、原子安装 smoke test。
- SARIF 输出；PR lint、变更 skill 行为测试、定时全量测试。

验收：全新临时目录可安装 Skill2 skills；重复安装可预测；无隐式脚本执行。

### M3：Usage

目标：把本地 Codex 日志转成可信事件。

- parser 与 Codex 日志 schema 解耦；fixture 驱动。
- 只统计当前 canonical skill 路径。
- 分类：activation、maintenance、broad scan、worker read、unknown。
- 记录 source、confidence、session、timestamp、harness、skill hash。
- session 内去重；排除 plugin cache、vendor、历史仓库。
- 默认只读本地；不上传 prompt、transcript、路径。

验收：能从真实 Codex 日志提取至少一个已知调用；人工核对误计数；重复运行不重复累计。

### M4：Report + Suggest

目标：把证据转成维护决策。

- 自包含静态 HTML：频率、最近使用、never-used、体积、共现、activation gap、false positive。
- 每个数字可追溯到事件或测试 run。
- 规则建议：keep、merge、downgrade、projectize、delete candidate。
- 低频高价值、项目 owner、测试覆盖作为 guardrail。
- 输出 JSON；不自动修改文件。

验收：对 `my-agent-config` 生成报告；复现已知的合并、降级、项目化决策；每条建议有证据。

### M5：0.1 发布

目标：别人可以安装并完成完整闭环。

- dogfood 全部 5 个 Skill2 skills。
- CLI help、错误信息、退出码、隐私说明稳定。
- 示例仓库与 golden report。
- Python package 发布；skills 安装脚本保留。
- changelog、版本、release artifact、安装 smoke test。

验收：新用户从安装到生成第一份报告，不需修改 Skill2 源码。

## 测试矩阵

| 层 | 内容 | CI |
| --- | --- | --- |
| Unit | parser、rules、assertions、dedupe | 每次提交 |
| Fixture | Codex JSONL、skill repo、危险样例 | 每次提交 |
| CLI | exit code、JSON schema、snapshot | 每次提交 |
| Integration | temp home/worktree、installer、report | PR |
| Live eval | 真实 Codex activation/outcome | PR 变更 skill 时；无凭证明确 skip |
| Drift | 固定 cases、多 trials、版本记录 | 定时 |

## 0.1 默认边界

- Runtime：Codex first。
- 格式：兼容 Agent Skills spec。
- CLI：Python 3.11+；`uv tool install`。首版不再引入 `npx`。
- 分发：通用 `skills/` 源码 + harness adapter。
- Usage：只读 Codex 本地日志。
- Report：本地静态 HTML，无 telemetry。
- Suggest：只读建议，无自动删除。
- Live eval：先单 harness；多 harness 留后续。

## 待确认

1. 是否接受 `Codex first`，0.1 不做 Claude/OpenCode live eval。
2. 是否接受 Python CLI，移除首版 `npx skill2 init` 承诺。
3. 是否接受 M0 → M5 顺序；每阶段都可独立发布和 dogfood。
4. 是否接受建议系统只输出 evidence，不自动改 skill library。

