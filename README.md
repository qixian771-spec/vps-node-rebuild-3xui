# vps-node-rebuild-3xui

面向 AI 执行者的 3x-ui REALITY 部署、迁移、排障与 Clash 手动出口技能。适用于自有服务器和已授权的客户端配置。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 能完成的任务

| 场景 | 方法与验收 |
|---|---|
| 3x-ui 重建/迁移 | 检查真实数据库模型、Vision flow、密钥配对、服务管理与实际代理出口 |
| 外部端口超时 | 外部探测、同步抓包、正常端口对照；区分本机与观测点前路径，不凭超时断言服务商封禁 |
| 多个节点整合进 Clash | 国内直连、国外跟随一个 GUI 手动选择；选中节点故障时阻断，不自动切换或直连 |
| Claude Desktop/CLI | 固定 HTTP 代理与显式加密 DNS 策略；分别验证配置、进程采用和网络路径 |
| 教程施工与交付 | 方案 → 任务卡 → 执行 → 测试 → 验收 → 提交；保留未测项与范围 |

## 结构

```text
SKILL.md                             入口、工作路径与关键约束
references/
  command-recipes.md                 按任务选择的操作示例
  troubleshooting.md                 症状、证据与下一步
  checklist-template.md              任务卡、里程碑、整体验收
  clash-routing-dns.md               单一出口、DNS、覆写、隔离故障测试
  claude-network.md                  Desktop/CLI 固定代理与保护边界
```

## 使用

把整个目录放入工具支持的技能目录；路径以该工具的官方配置为准。例如 Codex 的用户技能目录：

```sh
git clone https://github.com/qixian771-spec/vps-node-rebuild-3xui.git \
  ~/.codex/skills/vps-node-rebuild-3xui
```

也可以让执行者先读取 `SKILL.md`，按工作路径只加载需要的 references。不需要对已有安装重复 clone，也不需要为技能更新重新安装 VPS。

请求示例：

```text
使用 vps-node-rebuild-3xui，核对现有节点，把它们放入 Clash 的一个手动选择组。
国内直连，国外跟随我选择的节点，节点故障时连接失败，不自动换出口或直连。
同时核对 Claude Desktop 和 CLI 的代理与 DNS 路径，并给出实测结果和未测项。
```

## 版本与边界

经验包含 3x-ui 三表客户端模型，以及 2026-09-30 对 Mihomo 1.19.29、Clash Verge 2.5.2、Claude Desktop 2.16120.0 的实测。不是对全部 fork 或未来版本的兼容承诺；执行前核对当前 schema、官方文档和运行配置。

`SKILL.md` 的 Frontmatter 不绑定用户节点、IP、账号或密钥。所有示例只提供配置结构，不能直接用于生产。不要将真实配置、数据库、凭据或聊天内容提交到本仓库。

TUN、固定应用代理与系统级网络阻断是不同能力。技能要求报告实际范围，不保证任何状态下绝无泄漏，也不保证 Claude 账号不会受到风控。

## 贡献

Issue/PR 请说明触发条件、实际版本、观察证据、修改与验收方法。示例必须脱敏；明确区分“已配置”“已生效”“实测通过”。

[MIT](LICENSE) © 2026 qixian771-spec
