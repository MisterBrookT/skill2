<p align="center">
  <img src="docs/readme-icon.svg" width="88" alt="Skill2 图标">
</p>

<h1 align="center">Skill2</h1>

<p align="center"><strong>给 Skills 的 Skills。</strong></p>

<p align="center">
  一个可安装的 Skill Library，教 Agent 创建、测试、打包、发布、审计、可视化其他 Skill Library。
</p>

<p align="center"><a href="README.md">English</a></p>

<p align="center">
  <img alt="GitHub stars" src="https://img.shields.io/github/stars/MisterBrookT/skill2?style=flat-square">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-111111?style=flat-square">
  <img alt="本地数据" src="https://img.shields.io/badge/data-local--only-111111?style=flat-square">
  <img alt="MIT license" src="https://img.shields.io/github/license/MisterBrookT/skill2?style=flat-square&color=111111">
</p>

<p align="center">
  <img src="docs/readme-hero.svg" alt="Skill2 终端工作流">
</p>

## 安装

```bash
git clone https://github.com/MisterBrookT/skill2.git ~/.skill2 && ~/.skill2/install.sh
```

安装六个 Skill2 Skills 和辅助 CLI。依赖 Git 与 [uv](https://docs.astral.sh/uv/)。数据只留本地；无托管服务，无 telemetry。需要时可先检查 `~/.skill2/install.sh`。

从 checkout 运行时，安装器还支持 `--dry-run`；发现冲突后必须显式 `--force`。

Claude Code 安装到 `~/.claude/skills`：

```bash
~/.skill2/install.sh claude
```

`skill2 test --agent claude` 使用临时 `HOME` 与 `~/.claude/skills`。需要 API 配置时只复制 `~/.claude/settings.json`。

## Skill Library

| Skill | Agent 何时使用 |
| --- | --- |
| `skill2-create` | 创建、更新或重构 Skill。 |
| `skill2-test` | 隔离测试触发和结果。 |
| `skill2-package` | 生成可安装候选物；不写远端。 |
| `skill2-publish` | 准备 README、Release、公开安装检查。 |
| `skill2-audit` | 查找契约、安全、行为缺口。 |
| `skill2-visualize` | 查看库存、直接调用、零调用候选、测试状态，以及保守的生命周期复审候选项。 |

直接告诉 Agent：

```text
给这个工作流创建一个项目级 Skill。
审计这个 Skill Library，只给有证据的问题。
可视化哪些 Skills 被直接调用，哪些没有直接调用。
```

## 本地证据

Skill2 从本地 Agent session 日志识别精确 `SKILL.md` 读取，区分直接调用、批量扫描、维护、Worker 读取。APFS 不保存历史文件打开次数，因此 Skill2 不声称掌握完整使用历史。

直接在终端查看：

```bash
skill2 visualize --skills ~/workspace/my-skill-library/skills --codex ~/.codex
```

需要结构化输入时使用 `--json`。低频是证据，不是删除结论。输出不包含 prompt 或 transcript。

## 辅助 CLI

Skills 在需要确定性结果时调用：

```bash
skill2 scaffold skill my-skill --description "Use when ..."
skill2 scan skills --json
skill2 lint skills --format sarif
skill2 test skills/my-skill --cases cases/my-skill.yaml --baseline --trials 1
skill2 package-check .
skill2 publish-check .
skill2 usage --skills skills --codex ~/.codex --json
skill2 visualize --skills skills --codex ~/.codex
```

## 设计

Skill2 采用 Superpowers 型结构：Skills 是产品，CLI 是脚手架。仓库必须符合自己教的规则。Package 不发布。Publish 在 tag、push、Release、upload 前必须 dry-run 并获得明确确认。Visualize 不自动删除、移动或合并。

详见[设计](docs/DESIGN.md)与[先例调研](docs/PRIOR_ART.md)。

## 开发

```bash
uv sync
PYTHONPATH=src uv run python -m unittest discover -s tests
uv run ruff check .
uv run skill2 lint skills
```

MIT
