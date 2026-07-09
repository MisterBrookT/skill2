# 产品方向

## 核心判断

Skill2 首先是一个 **skill 包**。

CLI 是这些 skills 的确定性执行手。

```text
Skill2 skills：教 agent 怎么构建、测试、打包、发布、维护 skills。
Skill2 CLI：提供脚手架、lint、隔离测试、使用记录提取、报告生成。
```

所以产品不是“一个 CLI 加一些文档”，而是：

```text
别人把 Skill2 skills 装进自己的仓库
→ 他们的 agent 学会怎么 build/test/package/audit/prune skills
→ 需要确定性执行时再调用 skill2 CLI
```

## 目标用户

已经使用 Codex、Claude Code、OpenCode、Cursor 或类似 coding agent 的人。

他们想在自己的仓库里沉淀可复用 skills，但缺少方法：

- 怎么写一个好 skill
- 怎么测试它是否真的会触发
- 怎么隔离测试，避免当前会话/全局配置污染
- 怎么打包成别人好安装的开源 skill repo
- 怎么检查规范、断链、危险脚本、机器本地路径
- 怎么看哪些 skills 高频、低频、从未使用
- 怎么合并、降级、项目化、删除旧 skills

## 最终形态

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
    scaffold.py
    scan.py
    lint.py
    test.py
    usage.py
    report.py

  docs/
```

## Skill 包

### `skill2-build`

触发：用户想创建或改进一个 skill。

Agent 负责：

- 明确目标工作流
- 判断该做顶层 skill、reference，还是项目级 skill
- 写短而准的 `SKILL.md`
- 只在必要时添加 `references/`、`scripts/`、`assets/`
- 生成测试场景
- 调用 `skill2 lint`

### `skill2-test`

触发：用户问“这个 skill 有没有效”“会不会触发”“怎么隔离测”。

Agent 负责：

- 构造正例、邻近正例、反例、压力场景
- 用隔离环境只加载目标 skill
- 检查是否触发
- 检查不该触发时是否误触发
- 检查输出是否满足断言
- 解释失败原因

CLI 支持：

```bash
skill2 test ./skills/foo --agent codex --cases cases/foo.yaml --isolate
```

### `skill2-package`

触发：用户想把 skill repo 做成别人好安装的开源项目。

Agent 负责：

- 建立开源 repo 结构
- 写安装说明
- 检查跨 harness 兼容性
- 添加 license、changelog、示例
- 检查是否有 secrets、绝对路径、大文件、坏链接
- 需要时生成 plugin/marketplace metadata

CLI 支持：

```bash
skill2 scaffold skill-repo
skill2 lint --package
```

### `skill2-audit`

触发：用户想审计一个 skill library。

Agent 负责：

- 扫所有 skills
- 找长 description
- 找断链
- 找重叠/冲突触发词
- 找危险脚本
- 找过大的 skill
- 产出问题清单

CLI 支持：

```bash
skill2 scan ./skills --json
skill2 lint ./skills
```

### `skill2-prune`

触发：用户想清理 skill library。

Agent 负责：

- 读取 usage/report
- 找高频、低频、从未使用 skills
- 识别“应合并”“应降级为 reference”“应项目化”“可删除”
- 给理由和证据
- 不自动删除，必须人确认

CLI 支持：

```bash
skill2 usage --codex ~/.codex --json
skill2 report --out report.html
skill2 suggest --repo .
```

## CLI 职责

CLI 不是主要产品界面。Skills 才是。

CLI 只做确定性工作：

- 生成文件脚手架
- 校验 frontmatter/schema
- 估算 token
- 扫引用和断链
- 扫危险脚本
- 解析本地日志
- 跑隔离测试
- 生成静态 HTML 报告

Agent 做判断：

- 选 skill 范围
- 解释测试结果
- 决定合并/降级/项目化/删除建议
- 改写 skill 文本
- 说明取舍

## 安装故事

### 用户安装

推荐：

```bash
npx skill2 init
```

手动：

```bash
cp -R skills/skill2-* .agents/skills/
```

可选安装 CLI：

```bash
uv tool install skill2
```

### Agent 使用

安装后，用户可以说：

```text
帮我给这个 repo 写一个 skill
测试这个 skill 是否会触发
把这个 skill repo 做成别人好安装的开源仓库
看看我的 skill library 哪些该删
生成 skill 使用频率报告
```

Agent 触发 Skill2 skills；需要确定性检查时调用 CLI。

## 开源 skill repo 标准

推荐结构：

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

检查项：

- `SKILL.md` frontmatter 有效
- `name` 和目录名一致
- `description` 是短触发条件，不是工作流摘要
- `references/` 引用存在
- 需要执行的 scripts 有执行权限
- install 能复制 skills 到目标 harness 路径
- README 写清安装、使用、兼容性、隐私边界
- 没有 secrets
- 没有机器本地绝对路径
- 没有无用大文件

## 使用频率可视化

目标：让人看出 skill library 是否符合真实使用。

图表：

- 每个 skill 调用次数
- 最近使用时间
- 从未使用 skills
- 共现关系图
- skill 体积 vs 使用频率
- 隔离测试里的 activation gaps
- 反例测试里的 false positives
- 维护动作时间线

报告形式：

- 先做本地静态 HTML
- 不做服务器
- 不上传 telemetry

## 隔离测试

核心方法：

```text
目标 skill + 临时 skill root + 临时 home + 新会话 + 场景 prompt
```

测试分层：

- 核心正例：应该触发
- 邻近正例：应该触发
- 反例：不该触发
- 压力场景：容易误触发/漏触发
- 输出断言：触发后结果是否对

Codex first：

- 读到隔离路径下的 `SKILL.md` = activation candidate
- 如果 runtime 提供显式 activation event，则优先用显式事件
- 输出断言和 activation 检测分开

## 先例判断

Tripwire 已证明 activation coverage 可测：场景矩阵、真实 agent session、检测 skill 是否触发、CI 重跑。

Skill2 不应复制成另一个 CI-only linter。

Skill2 要组合：

- 给 agent 学的 skill 包
- CLI 脚手架
- 隔离测试
- 开源打包规范
- 本地使用记录分析
- pruning dashboard

## MVP 顺序

不要先做大而全 dashboard。

先做一条强闭环：

```text
agent 写 skill
→ CLI scaffold/lint
→ 隔离测试证明 activation
→ README 说明怎么安装
```

建议顺序：

1. `skills/skill2-build`
2. `skills/skill2-test`
3. `skill2 scaffold skill`
4. `skill2 lint`
5. `skill2 test --agent codex --isolate`
6. `skills/skill2-package`
7. `skill2 report` 静态 HTML
8. `skills/skill2-audit`
9. `skills/skill2-prune`

## 当前 repo 需要调整

当前 repo 仍偏 CLI-first。下一步应改成 skills-first：

```text
.agents/skills/isolated-skill-test/SKILL.md
```

迁到：

```text
skills/skill2-test/SKILL.md
```

再补：

```text
skills/skill2-build/SKILL.md
skills/skill2-package/SKILL.md
skills/skill2-audit/SKILL.md
skills/skill2-prune/SKILL.md
```

README 也要改成：

```text
Skill2 is a skill pack plus optional CLI for building, testing, packaging, auditing, and pruning agent skills inside your own repos.
```
