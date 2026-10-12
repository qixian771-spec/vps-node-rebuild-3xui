# vps-node-rebuild-3xui

供 AI 在没有历史聊天的情况下使用的执行技能：自有 3x-ui 节点部署/迁移/诊断、Clash 手动固定出口，以及按授权实施的 macOS DNS、浏览器和 Claude 网络保护。

**这是有门槛的执行手册与离线辅助工具，不是跨版本一键部署器。** 住宅代理账户不能当作 SSH 权限；源码/合成测试通过不代表真实 VPS、浏览器或应用已通过。

## 从哪里开始

| 需要 | 入口 |
|---|---|
| 首次或离线安装、已有安装更新 | [安装与首次使用](references/installation.md) |
| 让 AI 接收任务并选路 | [SKILL.md](SKILL.md) → [执行手册](references/runbook.md) |
| 参数、完整命令、退出码与版本适配卡 | [操作契约](references/operations.md) |
| 本次任务卡与分层证据 | [模板](references/checklist-template.md) |
| 本次交付的问题/任务卡/结果 | [审查与方案](docs/delivery-plan.md)、[验收记录](docs/acceptance.md) |

## 能力与实现边界

| 路线 | 实际实现 |
|---|---|
| R0 只读 | 环境/版本/配置/出口证据；检测不授予修改权限 |
| R1 服务端 | 版本适配、面板/受支持API操作手册；SQLite一致快照工具；无自动安装/直接SQL修复 |
| R2 排障 | 原基线、协议阶段、同窗对照、一次有界实验和停止条件 |
| R3 客户端 | 持久源/覆写/生成/运行一致性、手动出口、无自动换节点或直连DNS兜底 |
| R4 应用 | Claude固定代理的版本/路径确认与单日志证据工具；不发送Chat |
| R5 Mac防护 | DNS/浏览器分层流程、PF仅生成、本地WebRTC探针；不含PF自动加载器 |
| R6 重启 | 只覆盖获授权层级，保持selector；整机与GUI重启分开 |

国内 DIRECT 仅在用户选择时保留。失败显式停止依赖步骤；不自动重试、回滚、换来源/实现或降级验证。临时进程按任务卡预定方式清理。

## 快速安装验证

先取得这个仓库的完整目录，确认 Python ≥3.10。在该目录运行：

```sh
python3 scripts/skillctl.py validate
python3 scripts/skillctl.py --help
```

详细安装使用 `install --source <绝对源码目录> --destination <绝对新目录>`；父目录须存在，目的目录不得已存在，所有路径先核对且不含符号链接。完整安装说明见上表。manifest列出的入口、全部引用、资产/JS、辅助工具和许可一起安装；安装不需要root或网络。

示例请求：

> 使用这个 skill，只检查已有 Clash 的默认出口和 DNS，禁止切节点、重启应用或写配置；联网只允许明确列出的出口检测。先列证据与缺失项，检查完成后结束。

修改任务则明确要改的对象、默认出口/分流政策、允许的重载层级和成功标准；已有授权无需重复确认。所有敏感材料存私有目录，不进入仓库。

## 开发验证

```sh
python3 scripts/skillctl.py validate
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/webrtc.test.cjs
git diff --check
```

前三条也能在完整安装目录中执行；`git diff --check` 仅在Git源码检出中运行。

这些测试使用隔离目录、合成SQLite/日志和模拟ICE，不访问代理/VPS、不加载PF、不重启软件。GitHub Actions在Linux/macOS执行同样检查并验证包安装。真实业务检查必须单独取得授权并执行，不能拿CI代替。

专题中的旧版本与日期是历史案例，不能直接记入新任务的通过结果。技术依据使用目标精确版本官方文档/源码；禁止联网时没有这些材料就停止版本相关步骤。

[完整仓库](https://github.com/qixian771-spec/vps-node-rebuild-3xui) · [MIT](LICENSE)
