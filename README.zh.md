<p align="center">
  <img src="docs/readme-icon-v2.svg" width="88" alt="Skill2 图标">
</p>

<h1 align="center">Skill2</h1>

<p align="center">
  <strong>给 Skills 的 Skills。</strong><br>
  <strong>Agent Skill Library 全生命周期管理。</strong>
</p>

<p align="center">
  发布 Agent Skills 前完成测试与审计。在本地发现触发问题、证据不足与打包缺陷。<br>
  可视化整个 Skill Library 的使用情况与测试状态，并找出有证据支持的清理候选项。
</p>

<p align="center"><a href="README.md">English</a></p>

<p align="center">
  <img alt="GitHub stars" src="https://img.shields.io/github/stars/blackblue-labs/skill2?style=flat-square">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-111111?style=flat-square">
  <img alt="本地数据" src="https://img.shields.io/badge/data-local--only-111111?style=flat-square">
  <img alt="MIT license" src="https://img.shields.io/github/license/blackblue-labs/skill2?style=flat-square&color=111111">
</p>

<p align="center">
  <img src="docs/readme-hero.svg" alt="Skill2 终端工作流">
</p>

## 为什么需要 Skill2

写出一个 Skill 不难。维护二十个更难。

Skill Library 增长后，三个问题更重要：

- 该触发时是否触发，不该触发时是否保持安静？
- 它是否真的改善结果？
- 应该保留、修改，还是进入清理复审？

Skill2 把 Agent Skills 当成可测试、可审计的软件单元。五个专注 Skills 覆盖创建、测试、审计、打包与可视化；确定性脚本让证据可复现，并留在本地。

## 安装

### Claude Code

```text
/plugin marketplace add blackblue-labs/skill2
/plugin install skill2@skill2-marketplace
```

安装五个自包含 Skills。

### Codex

```bash
npx skills add blackblue-labs/skill2 -g -a codex -y
```

为 Codex 复制五个自包含 Skills。

### 手工 fallback

```bash
git clone https://github.com/blackblue-labs/skill2.git ~/.skill2 && ~/.skill2/install.sh
```

只复制 Skills（从 checkout 运行时 `install.sh` 支持 `--dry-run` 与冲突门控的 `--force`）。需要 Git。[uv](https://docs.astral.sh/uv/) 仅在 Skill 执行其确定性脚本时需要。Skill 脚本使用 `uv run --script`；首次运行可能将声明依赖拉取进 uv cache；离线使用需要已预热的 cache。数据只留本地；无托管服务、无 telemetry、用户无需 PyPI 安装。

## 五个专注 Skills

| Skill | Agent 何时使用 |
| --- | --- |
| `skill2-create` | 创建、更新或重构 Skill。 |
| `skill2-test` | 隔离测试触发和结果。 |
| `skill2-package` | 打包、编写公开文档，并按需发布 Skill 仓库。 |
| `skill2-audit` | 查找契约、安全、行为缺口。 |
| `skill2-visualize` | 查看库存、直接调用、零调用候选、测试状态，以及保守的生命周期复审候选项。 |

## 直接试用

告诉 Agent：

```text
给这个工作流创建一个项目级 Skill。
审计这个 Skill Library，只给有证据的问题。
可视化哪些 Skills 被直接调用，哪些没有直接调用。
```

## 本地优先证据

Skill2 从本地 Agent session 日志可视化 Skill 库存与使用情况。数据只留在你的机器；不包含 prompt 或 transcript。

## 设计

Skills 是产品；确定性脚本为 Skills 提供支持。仓库必须符合自己教的规则。Package 默认原生分发；只有用户需要时才增加 artifact 或 release 工作。Visualize 不修改 Skill Library。

| 方向 | 参考项目 | 采用内容 |
| --- | --- | --- |
| Skill 格式 | [Agent Skills spec](https://agentskills.io/specification)、[Anthropic Skills](https://github.com/anthropics/skills) | 可移植 `SKILL.md`、渐进加载、资源归属。 |
| 创建方法 | [Superpowers](https://github.com/obra/superpowers)、[writing-skills](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md) | Skills-first、触发优先、dogfood。 |
| 效果测试 | [Superpowers evals](https://github.com/prime-radiant-inc/superpowers-evals)、[Tripwire](https://github.com/bharath31/tripwire)、[Waza](https://github.com/microsoft/waza)、[skill-eval](https://github.com/fede0089/skill-eval)、[agent-skills-eval](https://github.com/darkrishabh/agent-skills-eval)、[skillci](https://github.com/tolztoy/skillci)、[skill-distill](https://github.com/lov-alt/skill-distill) | 隔离运行、正反路由、baseline、确定性断言。 |
| 打包分发 | [agent-scripts](https://github.com/steipete/agent-scripts)、[awesome-copilot](https://github.com/github/awesome-copilot)、[scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills)、[superpowers-marketplace](https://github.com/obra/superpowers-marketplace)、[Caveman](https://github.com/JuliusBrussee/caveman)、[OpenAI Plugins](https://github.com/openai/plugins) | 幂等安装、冲突门、marketplace manifest、CI。 |

感谢这些项目及其维护者。他们的工作深刻影响了 Skill2 的仓库架构与设计原则。

详见[设计](docs/DESIGN.md)与[先例调研](docs/PRIOR_ART.md)。

## 开发

贡献者与 CI 使用 checkout 内 CLI。这不是用户安装步骤：

```bash
uv sync
PYTHONPATH=src uv run python -m unittest discover -s tests
uv run ruff check .
uv run skill2 lint skills
uv run skill2 package-check .
```

MIT
