# Marketplace-first 安装设计

## 目标

用户安装 Skill2 后立即获得六个 Skills 及其确定性工具。不再要求额外安装全局 `skill2` CLI。

```text
Marketplace / npx / install.sh
                ↓
skills/skill2-*/SKILL.md + scripts/ + references/
                ↓
Agent 直接执行 Skill 自带脚本
```

Skills 是产品。顶层 Python package 只服务仓库开发、生成与验证。

## 设计依据

- [Superpowers](https://github.com/obra/superpowers#installation)：原生 marketplace 是主安装面；Skill Library 作为 plugin 分发。
- [Caveman](https://github.com/JuliusBrussee/caveman/blob/main/INSTALL.md)：Claude 使用 marketplace，Codex 使用 `npx skills add`；统一仓库适配不同发现入口。
- [Agent Skills specification](https://agentskills.io/specification)：Skill 目录拥有自己的 `SKILL.md`、scripts、references、assets；资源按需加载。
- [PEP 723](https://peps.python.org/pep-0723/)：单脚本声明 runtime 依赖，避免要求用户先安装项目 package。

取舍：采用原生安装与 Skill-owned resources；不采用独立 registry、全局 CLI 前置安装、六份手工维护实现。

## 安装面

### Claude Code：主入口

```text
/plugin marketplace add blackblue-labs/skill2
/plugin install skill2@skill2-marketplace
```

Plugin 安装整个仓库。六个 Skills、脚本、references 同时可用。

### Codex：Marketplace 目标，npx 当前入口

进入 OpenAI curated marketplace 后，README 使用 `/plugins` 作为主入口。进入前使用：

```bash
npx skills add blackblue-labs/skill2 -g -a codex -y
```

`npx skills add` 只复制 Skill 目录。因此每个 Skill 必须自包含，不得依赖仓库顶层 `src/`、`.venv` 或已安装的全局 `skill2` 命令。

### 手工 fallback

`install.sh` 只复制 Skills。保留 dry-run、冲突检查、原子替换；不再安装全局 CLI。

## Skill 目录

```text
skills/skill2-visualize/
├── SKILL.md
├── references/
└── scripts/
    ├── run
    ├── _runtime/
    └── .runtime-manifest.json
```

- `SKILL.md`：行为、判断、输出契约。
- `references/`：按需读取的重内容。
- `scripts/run`：Skill 唯一确定性入口。
- `scripts/_runtime/`：从顶层 canonical source 生成的最小模块集。
- `.runtime-manifest.json`：源文件、hash、依赖、生成版本。

无资源的 Skill 不创建空目录。

## Runtime 设计

### Canonical source

`src/skill2/` 仍是 Python 唯一编辑源。禁止手改 Skill 内 `_runtime/`。

### 生成

新增确定性同步器：

```bash
uv run python tools/sync_skill_runtime.py
uv run python tools/sync_skill_runtime.py --check
```

同步器读取显式映射：

| Skill | Runtime 能力 |
|---|---|
| `skill2-create` | scaffold |
| `skill2-test` | cases、runner、tester |
| `skill2-package` | scan、lint、package-check |
| `skill2-publish` | publish-check |
| `skill2-audit` | scan、lint |
| `skill2-visualize` | scan、usage、terminal report、suggest |

同步器计算本地 import closure，只复制所需模块。两个 Skill 使用相同模块时允许生成副本；副本由 hash gate 管理，不人工维护。

### 依赖

每个 `scripts/run` 使用 PEP 723 metadata，通过 `uv run --script` 获取声明依赖。用户需要 `uv`，但不需要安装 Skill2 package。

脚本从自己的 `_runtime/` import，不访问源码仓。离线使用依赖于机器已有 uv cache；README 明示该边界。

### 顶层 CLI

保留 `uv run skill2 ...` 供贡献者开发和 CI。它调用同一 canonical modules。README 将它放到 Contributor 区，不作为用户安装步骤。

## Skill 调用

每个 `SKILL.md` 使用相对路径：

```bash
uv run --script <skill-dir>/scripts/run -- <args>
```

Skill 不写 Claude/Codex 专用逻辑。Harness 只负责发现 Skill；脚本接口一致。

## Package / Publish 规则

`skill2-package` 新增硬门：

- 所有 `SKILL.md` 引用的脚本存在。
- `_runtime/` 与 canonical source hash 一致。
- installed Skill 脱离源码 checkout 后可运行。
- manifest 只声明已包含能力。

`skill2-publish` 新增公开安装门：

- Claude marketplace 安装 smoke。
- Codex `npx skills add` smoke。
- README 命令与 manifest 名称一致。
- 从公开来源重装后执行至少一个 Skill-owned command。

Tag、GitHub Release、registry 提交仍需用户再次确认。

## README

首屏只展示产品与原生安装：

1. Claude marketplace。
2. Codex `/plugins`；未上架前标注 `npx skills add`。
3. 手工 fallback 折叠到后面。

删除“安装六个 Skills 和辅助 CLI”。改为“安装六个 self-contained Skills”。开发 CLI 单独放 Contributor 区。

## 错误处理

- 缺 `uv`：脚本返回明确安装提示，不静默 fallback。
- runtime stale：package-check 失败，不发布。
- installed command 访问仓库路径：smoke 失败。
- marketplace 尚未上架：README 不宣称 `/plugins` 可搜索到 Skill2。
- npx 只装部分 Skills：每个被选 Skill 仍独立工作。

## 验证

### TDD

先写失败测试，再实现：

1. Skill 脱离源码仓仍能执行。
2. runtime source 改动后 `--check` 失败。
3. 重新同步后通过。
4. `install.sh` 不调用 `uv tool install`。
5. README 不要求全局 CLI。
6. Claude manifest 与 marketplace 本地 validate。
7. `npx skills add` 安装六个 Skills；删除 checkout 后运行 visualize smoke。

### 完成门

```bash
PYTHONPATH=src uv run python -m unittest discover -s tests
uv run ruff check .
uv run skill2 lint skills
uv run skill2 package-check .
uv run python tools/sync_skill_runtime.py --check
```

并在临时 HOME 完成 Claude、npx、install.sh 三条 clean-install smoke。

## 不做

- 不发布 PyPI 作为用户安装前提。
- 不自建 marketplace 服务。
- 不自动提交 OpenAI curated marketplace。
- 不在六个 Skill 中手工维护六份 Python 实现。
- 不在 Skill 正文复制 harness 差异矩阵。
