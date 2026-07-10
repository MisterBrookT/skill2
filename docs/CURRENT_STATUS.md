# Skill2 当前状态

更新：2026-07-10。

## 定位

Skill2 是 Superpowers 型 Skill Library。七个 Skills 管理其他 Skill Library。CLI 只做扫描、隔离测试、安装检查、usage 解析、报告生成。

## 已有

| 能力 | 状态 |
| --- | --- |
| scan/lint + JSON/SARIF | 完成 |
| Codex 隔离测试 + baseline/JUnit | 核心完成 |
| package/publish preflight | 核心完成 |
| Codex usage 日志适配器 | 完成 |
| HTML renderer + suggest | 完成；已接 CLI |
| `skill2-visualize` | 完成；核心/routing live trial 通过 |
| 专业安装/README | 完成；clean HOME smoke 通过 |
| 0.1 Release | 未完成 |

当前基线：42 个确定性 tests、Ruff 通过、七个 Skills lint clean。

## Usage 实测

扫描 `my-agent-config/skills` 与本地 Codex sessions：

- 200 个去重事件。
- 58 个 `activation`。
- 89 个 `broad_scan`。
- 48 个 `worker_read`。
- 4 个 `maintenance`。
- 1 个 `unknown`。

直接调用最高：`obsidian` 14、`agent-search` 13、`authoring-skills` 8、`about-me` 7、`academic` 4。

零直接调用候选：`clean-experiment`、`html-tunnel`、`navi-context`、`navi-deep-research`、`panel`、`report-builder`、`ship-oss-product`、`skill-repo-packaging`、`wechat-context`。

限制：精确读取 `SKILL.md` 是中等置信度调用代理。低频不等于删除。

## 为什么不做磁盘历史计数

APFS 不保存读取计数。FSEvents 不提供可靠读取事件。系统级监听只能记录启动后的读取，且权限高、噪声大。0.1 使用 Agent 日志；`usage watch` 留作 opt-in 研究项。

## 已修

- projectize 只认显式 metadata；source hub 路径不再作为证据。
- merge 只认直接 activation 共现；排除 broad scan。
- `visualize`、`suggest` 已接 CLI；已生成真实报告与 README 截图。
- installer 支持 dry-run、冲突拒绝、force、staging、provenance、CLI 安装。
- README 英中同步；七个 Skills；一个主安装命令。
- runner 每 trial checkpoint；支持 resume、skip-completed、early-stop。
- runner 使用随机 run id；macOS Seatbelt 拒绝宿主 HOME；PATH 去掉用户/repo 工具。
- visualize 核心测试相对 baseline 有 deterministic uplift；prune 相邻反例不再误触发。

## 已验证

- `package-check .`：通过。
- `publish-check .`：通过。
- clean HOME：dry-run、首次安装、重复安装、冲突拒绝、`--force` 覆盖通过。
- wheel/sdist 构建通过；当前版本仍是 `0.0.0`，产物不发布。

## 剩余阻塞

1. 全部 suites × 3 trials 未跑。
2. package scanner 的 repo-source 覆盖仍需独立 code/secret scanner。
3. 版本仍为 `0.0.0`；尚未生成 `0.1.0` artifact/checksum。
4. tag、Release、PyPI、公开 URL 重装未做。

## 本轮顺序

1. 跑全部 suites × 3 trials；失败项用 resume 续跑。
2. 升至 `0.1.0`，重建 artifact/checksum。
3. 输出 0.1 发布 dry-run。
4. 远端动作等用户确认。

## 安全门

- `suggest`、`prune` 不修改或删除 Skill。
- `visualize` 本地只读。
- usage 不输出 prompt、transcript、绝对路径。
- publish-check 不 tag、push、upload。
- 远端发布必须展示 dry-run 后再次确认。

## Git 状态

- 本地 checkpoint：`32b2a4c`。
- 远端尚未推送此 checkpoint。
