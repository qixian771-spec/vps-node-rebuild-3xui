# Mac DNS、WebRTC 与浏览器防绕行（已迁移）

本机端的完整施工与对账已经搬到独立仓库 **[claude-setup-kit](https://github.com/qixian771-spec/claude-setup-kit)**：Clash Verge 固定出口与 fake-ip DNS、PF 三道墙（Claude 精确 IP、Anthropic 整段、物理 DNS/STUN 与本用户公网只走 TUN）、自检守护、地址更新器、IPv6 守护、Chrome WebRTC/DoH 描述文件、时区，每一项都有只读对账（`mirror_check.py`）和双击安装器，最终以 <https://ippure.com/claude.html> 四项验收。本仓库只保留节点侧与下面的对照。

| 原本这里的内容 | 现在在哪 |
|---|---|
| 系统 DNS 接入本地解析、"系统 DNS 地址不等于最终上游"（Clash Verge 开 TUN 会把系统 DNS 写成 114.114.114.114，真正的路径是 TUN 劫持 53 + PF 封物理 53/853） | claude-setup-kit [执行手册 S1](https://github.com/qixian771-spec/claude-setup-kit/blob/main/references/runbook.md)，对账 id `clash.dns`、`dns.local53`、`dns.system`、`dns.upstream` |
| Chrome 管理策略（WebRtcIPHandling、DnsOverHttpsMode）、Safari | 手册 S9；策略必须用描述文件装，手工写 `/Library/Managed Preferences` 会被系统清掉；Safari 靠 PF UID 规则 |
| PF 防绕行与持久化 | 手册 S2–S4；本仓库仍保留只生成不加载的模板 [macos-leak-guard.pf.in](../assets/macos-leak-guard.pf.in)（`skillctl render-pf`） |
| 重启验收、TCP 正常 UDP 丢失 | 手册 S6 自检守护（60 秒复查）与 `mirror_check --only dns.local53`（UDP 与 TCP 分别验证） |
| 分层验收与停止条件 | 手册第 3 节退出码表与第 4 节情景推演；[ippure 验收](https://github.com/qixian771-spec/claude-setup-kit/blob/main/references/ippure-acceptance.md) |

硬规则不变：出口节点固定不切、不向 Anthropic 地址做直连试探、所有写系统的动作由用户双击执行并由 AI 读日志对账。
