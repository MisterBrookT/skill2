# Skill2

给 skill 的 skill。

Skill2 是本地技能库维护工具：检查 skill 文件、统计真实调用、可视化高频/低频 skill，并建议保留、合并、降级、项目化或删除。

[English](README.md)

## 状态

设计仓库。CLI 还未发布。

## 为什么做

Agent skills 正在变成 package-like 的东西。技能库也需要像代码一样维护：

- lint：frontmatter、description、断链、危险脚本
- coverage：哪些 skill 真的触发过
- analytics：高频、低频、从未调用、共现
- pruning：删除、合并、降级为 reference、移动到项目级

现有工具多停在校验。Skill2 做治理闭环。

## 计划命令

```bash
skill2 scan ~/workspace/my-agent-config/skills --json > skill2-scan.json
skill2 usage --codex ~/.codex --claude ~/.claude --opencode ~/.config/opencode --json > skill2-usage.json
skill2 test ./skills/agent-search --agent codex --cases cases/agent-search.yaml --isolate
skill2 report --scan skill2-scan.json --usage skill2-usage.json --out report.html
skill2 suggest --repo ~/workspace/my-agent-config
```

## 核心层

| 层 | 输出 |
| --- | --- |
| 扫描 | 结构问题、token 体积、引用、脚本、重复描述 |
| 使用 | 从本地 harness 日志或 hook 抽 skill 调用候选 |
| 测试 | 隔离场景运行：应触发、不应触发、输出断言 |
| 质量 | 路由测试、混淆矩阵、Hit@1/Hit@5 |
| 报告 | 高频/低频/未用 skill 和风险 |
| 建议 | 保留、合并、降级、项目化、删除 |

## 第一目标

复现一个真实维护决策：

`search-strategy`、`smart-fetch`、`internet-reach` 应从顶层 skill 降级到 `agent-search/references/`。

## 文档

- [最小版本](docs/MVP.md)
- [架构](docs/ARCHITECTURE.md)
- [隔离测试](docs/ISOLATED_TESTING.md)
- [先例调研](docs/PRIOR_ART.md)

## License

MIT
