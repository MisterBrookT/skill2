# `skill2-build` Dogfood: `build-core`

同一 prompt；两个隔离 Codex session；各 1 次。

| 运行 | 安装 Skill | activation | outcome |
| --- | --- | --- | --- |
| [with-skill](with-skill.md) | `skill2-build` | pass；精确读取 `SKILL.md` | pass |
| [baseline](baseline.md) | 无 | 不检查 | pass |

Prompt：

```text
帮我设计一个管理 API 文档的 agent skill。先判断 scope，再给 SKILL.md 和测试场景；不要改文件。
```

结论：自动测试只证明 `skill2-build` 被触发。baseline 也完成输出，所以没有证明 Skill 带来增益。人工审阅两份原始回答后，在 [DOGFOOD.md](../../../../docs/DOGFOOD.md) 填结论。

原始输出逐字复制；不修正其中的错误、冗余或异常文字。
