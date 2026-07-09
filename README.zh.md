<p align="center">
  <img src="docs/readme-icon.svg" width="96" alt="Skill2 icon">
</p>

<h1 align="center">Skill2</h1>

<p align="center">
  给 skill 的 skill。
</p>

<p align="center">
  一个 skill 包，附带可选 CLI，用来在你的仓库里构建、测试、打包、审计、清理 agent skills。
</p>

<p align="center">
  <a href="README.md">English</a>
</p>

<p align="center">
  <img alt="GitHub stars" src="https://img.shields.io/github/stars/MisterBrookT/skill2?style=flat-square">
  <img alt="License" src="https://img.shields.io/github/license/MisterBrookT/skill2?style=flat-square">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-1f2933?style=flat-square">
  <img alt="Local first" src="https://img.shields.io/badge/local--first-no%20telemetry-2dd4bf?style=flat-square">
</p>

<p align="center">
  <img src="docs/readme-flow.svg" alt="Skill2 workflow">
</p>

## 为什么做

Agent skills 正在变成类似 package 的东西。一个仓库可以携带可复用的 instructions、references、scripts、tests，让 agent 学会怎么在这个仓库里工作。

Skill2 给这一层补维护闭环：创建 skill，测试是否触发，打包给别人安装，审计整个库，清理不再值得保留的 skill。

## 安装

```bash
curl -fsSL https://raw.githubusercontent.com/MisterBrookT/skill2/main/install.sh | bash -s -- codex
```

这会把 Skill2 skill 包安装到 `~/.agents/skills`。无 telemetry。无托管服务。

## Skill 包

| Skill | 用途 |
| --- | --- |
| `skill2-build` | 创建或改进 skill。 |
| `skill2-test` | 隔离测试触发和输出。 |
| `skill2-package` | 把 skill repo 做成可安装包。 |
| `skill2-audit` | 扫描 skill library 的结构和安全问题。 |
| `skill2-prune` | 建议保留、合并、降级、项目化、删除。 |

## CLI

CLI 是给 skills 调用的确定性助手。

已实现：

```bash
skill2 scaffold skill my-skill --description "Use when ..."
skill2 lint skills
skill2 scan skills --json
```

计划：

```bash
skill2 test ./skills/my-skill --agent codex --cases cases/my-skill.yaml --isolate
skill2 usage --codex ~/.codex --json
skill2 report --out report.html
skill2 suggest --repo .
```

## 本地检查

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m skill2.cli lint skills
```

## 文档

- [产品方向](docs/PRODUCT_DIRECTION.md)
- [最小版本](docs/MVP.md)
- [架构](docs/ARCHITECTURE.md)
- [隔离测试](docs/ISOLATED_TESTING.md)
- [先例调研](docs/PRIOR_ART.md)
- [热门 skill 仓库结构参考](docs/SKILL_REPO_REFERENCES.md)

## 状态

早期。Skill 包已存在。CLI 支持 scaffold 和 lint。下一步是隔离运行时测试、usage 解析、dashboard 报告。

## License

MIT
