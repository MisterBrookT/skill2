# 当前状态

> 更新：2026-07-13（Task 6：三条 clean-install smoke）

## 产品

Skill2 = 六个自包含 Skills（create / test / package / publish / audit / visualize）。用户安装后直接获得 Skills 与 Skill-owned 脚本；不要求全局 `skill2` CLI。

## 公开安装（已文档化 + smoke 验证）

| 入口 | 命令 / 动作 | 状态 |
| --- | --- | --- |
| Claude Code 主入口 | `/plugin marketplace add MisterBrookT/skill2` + `/plugin install skill2@skill2-marketplace` | README 主路径；本地 marketplace + plugin install smoke 通过（临时 HOME） |
| Codex 当前 | `npx skills add MisterBrookT/skill2 -g -a codex -y` | 文档化 + 本地源 smoke 通过；**未**宣称 curated `/plugins` 可搜索 |
| 手工 fallback | `git clone … && ./install.sh` | Skills-only；无 `uv tool install`；smoke 通过 |
| 贡献者 CLI | `uv run skill2 …` | 仅 Development / CI |

`uv`：仅当 Skill 执行确定性脚本时需要。无托管服务、telemetry、PyPI 用户安装前提。

## Clean-install smoke 证据（Task 6）

工具：`tools/smoke_install.py`（`--mode install-sh|npx|claude|all`，checkpoint 可 `--resume`）。

| mode | run-id | 结果 | 验收 |
| --- | --- | --- | --- |
| `install-sh` | `20260713T133517Z-39708f2a` | completed | 六 Skills 装入 temp HOME；detach 后 `skill2-create/scripts/run` scaffold 成功 |
| `npx` | `20260713T133520Z-6a24dca4` | completed | 六 Skills → Codex `~/.agents/skills`；detach 后 `skill2-visualize/scripts/run` 出终端 inventory |
| `claude` | `20260713T133524Z-6395eaad` | completed | 本地 marketplace add + `skill2@skill2-marketplace` install；detach 后 Skill-owned scaffold 成功；无 model/API |

Checkpoint 目录：`.skill2/install-smoke/<run-id>/`（gitignore）。manifest 不含真实 HOME / prompt / transcript / token。

## 已完成（本分支进展）

- Skill runtime bundle：`scripts/run` + `_runtime/` + hash gate（Tasks 1–3）。
- Installer 与 Skill 文档脱离全局 CLI（Task 4）。
- 公开 README / package-publish 规则 / DESIGN 对齐 marketplace-first（Task 5）。
- 三条 clean-install smoke 与 resumable 证据落盘（Task 6）。

## 未完成 / 外部条件

- Codex curated marketplace **未提交**；上架前 README 保持 `npx skills add`，不宣称 `/plugins` 可搜到 Skill2。
- 未做 tag、GitHub Release、PyPI upload、marketplace 远端提交。

## 版本

- 项目与 plugin manifest：`0.1.0`
