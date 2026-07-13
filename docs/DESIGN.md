# 设计

## 定位

Skill2 是可安装的 Skill Library。六个 Skills 管理其他 Skill Library；Python CLI 只提供确定性脚手架。

```text
create → test → package → publish
             audit
                    visualize
```

## 仓库结构

```text
skills/<name>/SKILL.md   Agent 行为；产品主体
src/skill2/              scan、lint、test、usage、report
cases/*.yaml             扁平的机器测试输入
tests/                   CLI 确定性测试
docs/                    prior art 与设计依据
.skill2/                 本地运行证据；不提交
```

每个 Skill 使用独立目录，因为发现、安装、版本与资源归属都以 Skill 目录为单位。即使当前只有 `SKILL.md`，以后需要的 `references/`、`scripts/`、`assets/` 仍由同一 Skill 持有。没有资源时不创建空目录。

可选 UI metadata 不默认生成。只在目标分发格式明确要求时添加。

## 职责

| Skill | 负责 | 不负责 |
| --- | --- | --- |
| `skill2-create` | 创建、更新、拆分、合并 Skill | 行为 trial、打包、发布 |
| `skill2-test` | 隔离测试 activation 与 outcome | 修改 Skill |
| `skill2-package` | 生成并检查可安装候选物 | 远端写入 |
| `skill2-publish` | README、release、公开安装验证 | 未确认的 tag、push、upload |
| `skill2-audit` | 发现格式、安全、职责与行为缺口 | 自动修复、生命周期决策 |
| `skill2-visualize` | 终端展示 inventory/usage/test evidence；可选保守生命周期 review candidates | 写报告文件、自动删除/移动/合并 |

## 设计来源与取舍

### `skill2-create`

参考：

- [Agent Skills spec](https://agentskills.io/specification)：目录、frontmatter、渐进加载的兼容基线。
- [Anthropic skills](https://github.com/anthropics/skills)：按需组织 `references/`、`scripts/`、`assets/`。
- [Superpowers `writing-skills`](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md)：先判断是否值得创建 Skill；`description` 只写触发条件。

采用：

- **Scope first**：先选顶层 Skill、现有 owner 的 reference、project-local 或 no skill，避免顶层 namespace 膨胀。
- **Trigger first**：名称和 `description` 描述用户意图；流程留正文，迫使 Agent 触发后读取完整规则。
- **Progressive disclosure**：核心判断留 `SKILL.md`；大段领域资料、重复执行和交付资产按需拆分。
- **Freedom matching**：开放问题给原则；重复、脆弱、可验证动作交给 script 或 validator。
- **Minimal files**：不创建空目录或可选 metadata，除非目标分发格式明确要求。

取舍：

- Create 只负责 authoring，不运行昂贵 behavior trial；效果验证交给 `skill2-test`。
- 不复制 Superpowers 完整 pressure-testing 流程；Skill2 默认一次 trial + 人工看产物。
- 不依赖某一个 harness 的内置 creator；同一 Skill 源应跨 harness 使用。
- 不混入 package、publish、release；避免触发重叠和远端副作用。

### `skill2-test`

参考：

- [Superpowers evals](https://github.com/prime-radiant-inc/superpowers-evals)、[Tripwire](https://github.com/bharath31/tripwire)：真实场景、正反例、activation 与 outcome 分离。
- [Waza](https://github.com/microsoft/waza)、[skill-eval](https://github.com/fede0089/skill-eval)：多次运行、隔离 workspace、baseline 与 grader 分层。
- [agent-skills-eval](https://github.com/darkrishabh/agent-skills-eval)、[skillci](https://github.com/tolztoy/skillci)：with/without 对照、artifact shape、确定性断言。

采用：

- **Activation 与 outcome 分测**：读到 Skill 不代表结果更好；两者分别判定。
- **Target-only**：只安装目标 Skill，测它能否触发、产生要求的文件或回答、相对 baseline 是否有增益。
- **Pack routing**：安装同库所有候选 Skills，测相邻职责是否抢触发；单 Skill 环境不能证明 sibling routing。
- **Without-skill baseline**：同一请求不安装 Skill 再跑一次；baseline 也通过时，不宣称确定性增益。
- **结构化断言**：优先检查文件、命令、事件和字段；少用容易被关键词投机的文本包含判断。
- **原始证据**：events、最终输出、workspace、模型版本与 Skill hash 留在 ignored `.skill2/`，供人工复核。

取舍：

- 默认一次 trial；只有已知随机性或重要回归才增加次数，不把成本当质量。
- 不做首版模型矩阵；先证明单一 runner 的隔离与证据链正确。
- **精确读取隔离 `SKILL.md` 只算 medium confidence**：它证明模型打开了文件，但不证明 harness 正式激活 Skill、读完正文或遵循规则。只有 harness 提供明确 activation event 时才算 high confidence。
- **强制把 Skill 内容塞进 prompt 不算自然 activation**：它只能测内容是否有用，不能测 description 路由是否有效。
- 静态 description 相似度只用于发现候选冲突，不能代替真实 Agent run。
- 测试失败只记录证据；不自动改写或删除 Skill。

### `skill2-package`

参考：

- [Agent Skills spec](https://agentskills.io/specification)、[Anthropic skills](https://github.com/anthropics/skills)：可安装 Skill 与资源目录的基础形状。
- [Superpowers](https://github.com/obra/superpowers)：skills-first、多 harness manifest、测试与分发分层。
- [agent-scripts](https://github.com/steipete/agent-scripts)：路径 adapter、幂等同步、冲突可见。

采用：

- 通用行为只放 `skills/`；harness metadata 由 adapter 生成，不复制多份 Skill 正文。
- 安装前显示目标路径与计划写入；发现已有文件时阻止覆盖，除非用户显式 `--force`。
- 重复安装结果可预测；同版本、同内容不制造额外状态。
- 在临时 HOME 做 clean-install smoke，验证陌生机器路径，不依赖开发机缓存。
- artifact 绑定 version 与 checksum，保证 Publish 操作的是同一候选物。

取舍：

- 不复制 prior-art 仓库的个人目录假设；安装位置由目标 harness adapter 决定。
- 不自动执行第三方 Skill 附带脚本；可安装不等于脚本已获执行授权。
- workspace 被信任不等于所有工具和网络动作被授权。
- Package 无远端副作用；tag、push、release、upload 全部归 Publish。

### `skill2-publish`

参考：

- [agent-scripts](https://github.com/steipete/agent-scripts)：透明安装、冲突处理、不同环境路径适配。
- [awesome-copilot](https://github.com/github/awesome-copilot)：schema 与 CI gate 先于公开分发。
- [superpowers-marketplace](https://github.com/obra/superpowers-marketplace)：marketplace manifest 保持薄层，Skill 内容仍由源仓库维护。

采用：

- README 只承诺已交付能力，给陌生用户一个主安装路径、兼容性、隐私与限制。
- 发布前检查 package、tests、CI、working tree、version、changelog、artifact 与 checksum。
- 所有远端动作先输出精确 dry-run，再获得用户显式确认。
- 发布后从公开 URL 重新安装，验证 README、manifest、installer 与 release 指向同一版本。

取舍：

- Publish 不重做 package 内部；候选物失败时退回 Package。
- 不把用户说“发布一下”解释成对所有 tag、push、registry 自动授权；远端动作逐项可见。
- 支持发布到现有 registry/marketplace，但不在 Skill2 内自建 registry 服务。

### `skill2-audit`

参考：

- [skillci](https://github.com/tolztoy/skillci)、[Tripwire](https://github.com/bharath31/tripwire)：格式、安全、fixtures 与 CI 检查。
- [skill-distill](https://github.com/lov-alt/skill-distill)：description 质量与静态 overlap 候选。
- [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills)：大型 Skill Library 扫描与资源安全。

采用：

- **Deterministic CLI first + semantic review**：先跑 `skill2 lint <target> --json` 拿静态证据，再人工补 description 语义、ownership、scope 与 trigger overlap。
- **单 Skill audit**：检查 frontmatter、description、断链、resources、scripts、secrets、本机路径与正文体积。
- **Library audit**：对每个 Skill 执行单体检查，再查重复名称、ownership、project/global scope 与静态 trigger overlap。
- 使用 P0–P3 区分会坏、会误触发、安全/维护风险、清理债务。
- 输出具体文件、证据、影响与最小修复建议；默认不修改。

取舍：

- CLI 覆盖结构/安全/断链等可证明项；语义边界仍需人审。CLI 不可用或失败时标 limitation/`inconclusive`，不得宣称 clean。
- 不执行不可信脚本；Audit 检查文本、权限和命令模式，不通过运行它来“验证”。
- 不自动修复；用户确认后由 Create 或普通编辑流程应用变更。
- 静态 overlap 只表示值得测试，不证明真实误触发；live routing 归 Test。
- Audit 找问题，不决定保留或删除；生命周期判断归 Visualize。

### `skill2-visualize`

参考：

- Agent Skills 本地目录模型：inventory 来自当前 Skill 根目录，不依赖远端 registry。
- 测试项目的结构化 evidence：test status 来自现有 run 结果，不由展示层推断。
- Skill2 本地 usage 数据：direct、broad scan、maintenance、worker read 分开。当前没有直接照搬的成熟 visualization 项目。
- [skill-distill](https://github.com/lov-alt/skill-distill)：description overlap 与合并候选发现。
- Tripwire、skill-eval：测试证据必须与静态判断分开。
- Skill2 本地 usage：调用次数、最近时间、事件类别与 confidence。

采用：

- 默认直接输出终端表格，用户无需打开浏览器或管理报告文件。
- `--json` 输出同一证据模型，供 Agent 解释或脚本继续处理。
- 展示 inventory、direct calls、last direct call、test status 与相对频率条。
- 明确标记 `never`、`missing` 和证据限制，不用空值推断结果。
- **Deterministic evidence first + human lifecycle judgment**：每个正常工作流先跑终端 `skill2 visualize` 与只读 `skill2 suggest --json`，先呈现证据，再摘要保守 review candidates；详细解释（confidence、反证、可逆下一步）见 `references/lifecycle-suggestions.md`。
- 每个 usage event 保留 source 与 confidence，避免把启发式证据伪装成事实。
- 精确直接读取、批量扫描、维护写入、worker read 分开统计；只有前者接近真实调用。
- 结合 ownership、tests、依赖、项目边界与用户上下文，不只看频次。
- 建议限定为 keep、merge、downgrade、projectize、delete candidate，并附证据、反证和下一步。

取舍：

- 不生成 HTML 或持久报告文件，降低使用摩擦和维护成本。
- 不输出 prompt、transcript、绝对路径；展示只需要聚合后的本地证据。
- Visualize 呈现证据并可选摘要 lifecycle review candidates；不自动 apply keep/delete/merge。
- zero-direct 只表示当前 adapter 没发现直接读取，不表示 Skill 从未使用。
- CLI 给确定性候选；生命周期最终判断仍归人，不自动 apply。
- 不做云端 telemetry；日志与报告留本地，不上传 prompt 或 transcript。
- 低频不等于无用；灾难恢复、发布等高价值低频 Skill 在有测试或关键工作流支撑时可保留。
- delete 只是候选，不是动作；不自动删除、移动或合并文件。
- CLI/证据不可用或失败时降低置信度或标 `inconclusive`，不编造 usage/test 结果。
- 原独立生命周期 Skill 已并入 Visualize：触发重叠、共享证据管线，一条产品路径即可完成“看证据 + 保守 review”。

完整调研与链接见 [PRIOR_ART.md](PRIOR_ART.md)。
