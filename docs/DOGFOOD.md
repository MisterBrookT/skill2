# Skill2 Dogfood

目标：自动测试筛错；用户确认实际价值。

## 协议

1. 每 Skill 跑一个隔离 `with-skill` trial；正例另跑 baseline。
2. 看原始最终回答、workspace artifact、activation evidence；不只看 pass/fail。
3. 每张卡记录：保留 / 改写 / 拆分 / 合并 / 删除；写一句原因。
4. 发现误触发、漏触发、无价值输出：新增或改写 case，再重跑。
5. 未人工签结论，不算 dogfood 通过。

## 验收卡

| Skill | 应该交付 | 不该做 | 状态 |
| --- | --- | --- | --- |
| `skill2-build` | 判断 scope；写短、可测 Skill 结构 | 把 reference 拆成新 Skill | 待验收 |
| `skill2-test` | 隔离协议；activation/outcome/baseline 边界 | 把当前 chat 当证据 | 待验收 |
| `skill2-package` | 可安装候选物、manifest、smoke | tag/push/release | 待验收 |
| `skill2-publish` | README、发布 preflight、确认门 | 未确认远端写入 | 待验收 |
| `skill2-audit` | P0-P3 证据问题清单 | 直接修改目标 | 待验收 |
| `skill2-prune` | 保留/合并/降级/项目化候选与证据 | 自动删除 | 待验收 |
| `skill2-visualize` | 本地 HTML：库存、usage、测试 | 采集/上传数据、替 prune 决策 | 待验收 |

## 证据格式

```text
Skill:
Case:
with-skill artifact:
baseline artifact:
结论: 保留 / 改写 / 拆分 / 合并 / 删除
原因:
新增 case:
```

## 通过门

- 自动：目标 case `1 trial` 通过；无 runner error。
- 人工：用户确认产物真有用；边界正确；无危险动作。
- release：七张卡都有明确结论。
