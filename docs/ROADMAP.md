# Skill2 路线图

## 目标

发布一个 Superpowers 型 Skill Library：七个 Skills 管理其他 Skill Library；CLI 只提供确定性脚手架。

```text
build → test → package → publish
  ↓       ↓        ↓
audit → prune → visualize
```

## 产品面

```text
skills/
  skill2-build/
  skill2-test/
  skill2-package/
  skill2-publish/
  skill2-audit/
  skill2-prune/
  skill2-visualize/

src/skill2/       # Skills 调用；不是主产品叙事
cases/            # 七个单 Skill suites + 整包 routing
docs/             # 规范、prior art、边界
install.sh        # 一个主安装入口
README.md         # 公开发布界面
```

## 不变量

- `skills/<name>/SKILL.md` 是行为单一来源。
- `description` 写触发，不写流程摘要。
- Activation 与 Outcome 分测。
- 每个 trial 新临时环境。
- Package 无远端副作用。
- Publish 远端动作先 dry-run，再显式确认。
- Usage 默认本地；不输出 prompt、transcript、绝对路径。
- Prune 只建议，不删除。
- Visualize 只读，不采集。
- Skill2 自己通过全部规则。

## 当前执行

### M0：库存与规则

状态：完成。

- `scan`：结构化库存、hash、resources、scope。
- `lint`：ERROR/WARN/ADVICE、JSON、SARIF。
- YAML/Markdown 正式解析。
- CI 与 fixtures。

### M1：隔离测试

状态：核心完成；进入轻量 dogfood。

- 临时 `HOME/CODEX_HOME`。
- 单 Skill 与整包安装。
- activation/outcome/baseline/JUnit/原始证据。
- 七个单 Skill case 文件；整包 routing。

已完成：resume、skip-completed、early-stop。待办：每 suite `1 trial` + 人工审阅原始产物。

### M2：Package + Publish

状态：完成。

- `scaffold skill-repo`
- `package-check`
- `publish-check`

- installer：`--dry-run`、冲突报告、staging、原子替换、provenance。
- clean HOME：首次安装、重复安装、冲突拒绝、`--force` 覆盖 smoke 通过。
- `package-check`、`publish-check` 对 Skill2 自身通过。

### M3：Usage

状态：Codex 日志适配器完成。

- `activation` / `broad_scan` / `maintenance` / `worker_read` / `unknown`。
- session 内去重。
- Skill 名输出；不泄露 prompt、transcript、绝对路径。

不做：从 APFS/FSEvents 回溯读取次数。

研究项：opt-in `usage watch`。只监听启动后的读取；不阻塞 0.1。

### M4：Visualize + Suggest

状态：完成；已接 CLI、修规则、真实 dogfood。

- 新增 `skill2-visualize`。
- `skill2 visualize --skills <path> --codex <path> --out <html>`。
- 合并 scan、usage、test、suggest。
- 直接调用与扫描噪声分开显示。
- 每个数字可追溯到事件。
- 低频只生成候选，不自动删除。

验收：对 `my-agent-config` 生成真实 HTML；人工抽查频率和零调用名单。

### M5：0.1 Dogfood 发布

状态：进行中。

1. 完成：七个 Skills lint clean。
2. 待办：七个隔离 suites × 1 + 整包 routing × 1；人工审阅。
3. 完成：Skill2 自己通过 package/publish/audit。
4. 完成：README 英中双语；一个主安装命令；真实报告预览。
5. 完成：clean install、重复安装、冲突、dry-run smoke。
6. 待办：版本升至 `0.1.0`，重建 wheel/sdist 与 checksums。
7. 待办：输出发布 dry-run。
8. 用户确认后才 tag、push tag、GitHub Release、PyPI upload。
9. 待办：从公开 URL 重装。

## CLI 目标

```bash
skill2 scaffold skill <name>
skill2 scaffold skill-repo <name>
skill2 scan <path> --json
skill2 lint <path> --format text|json|sarif
skill2 test <skill> --cases <file> --baseline --trials 1
skill2 package-check <repo>
skill2 publish-check <repo>
skill2 usage --codex ~/.codex --skills <library> --json
skill2 visualize --codex ~/.codex --skills <library> --out report.html
skill2 suggest --codex ~/.codex --skills <library> --json
```

## 七 Skill 自测门

| Skill | 强反例 | Outcome |
| --- | --- | --- |
| `skill2-build` | test/package | 生成 Skill + cases；lint 通过 |
| `skill2-test` | build/audit | 隔离；activation/outcome 分离 |
| `skill2-package` | publish | 可安装候选物；无远端副作用 |
| `skill2-publish` | package | README/release preflight；确认门存在 |
| `skill2-audit` | prune/visualize | 分级问题；不修改 |
| `skill2-prune` | audit/visualize | 证据建议；不删除 |
| `skill2-visualize` | audit/prune | 本地 HTML；不采集、不修改 |

每个 Skill：正例、改写、邻接反例、无关反例、Outcome、without-skill baseline、1 trial、人类验收。

## 完成定义

新用户执行一个安装命令；Agent 能发现七个 Skills；能扫描、测试、打包、发布检查、统计、生成报告；不改 Skill2 源码；不上传本地证据。
