# vps-node-rebuild-3xui

> **给 AI 用的 3x-ui（x-ui）REALITY 节点「重建 / 迁移 / 排障」技能包。**
> 把踩过的坑写成 AI 能直接执行的步骤 —— 让它一次做对，而不是陪你试三小时。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![3x-ui](https://img.shields.io/badge/3x-ui-3.8.x-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Ubuntu%2022.04%2B-orange.svg)

---

## 这是什么

一个 **Agent Skill**（AI 技能包）。把它装进你的 AI 助手，或直接把 `SKILL.md` 丢给任意 AI，
它就能在你重建 / 迁移 / 排障 3x-ui 节点时，**按正确顺序、避开已知的全部坑**。

**它不是教程，是"操作手册 + 排错表"** —— 面向的是**执行者**，而不是读者。

## 它解决什么（这些坑我们都踩过）

| # | 坑 | 典型症状 | 代价 |
|---|---|---|---|
| 1 | **客户端凭据存三张表**（`clients` + `client_inbounds` + `client_traffics`）| 进程正常、端口在听，**但认证必失败**；`config.json` 里 `clients: []` | 配置看起来全对却连不上，最容易卡在这里 |
| 2 | **`flow` 来自 `client_inbounds.flow_override`** | 补了客户端表，**仍然完全不通**（`http_code=000`）| Vision 缺 `flow` 等于白配 |
| 3 | **Ubuntu 上 BBR 是模块 `tcp_bbr`** | `lsmod \| grep bbr` 查不到 → 误判"不支持"；`modprobe bbr` 报错 | 延迟白白多 100ms+ |
| 4 | **面板 CLI 常无修改子命令** | `x-ui setting -port ...` 只打印帮助 | 改不了面板端口/账号 |
| 5 | **2FA 存在 `settings` 表**（`users` 表里没有）| 找不到 2FA 字段，不知道怎么配；配了也不知道成没成 | 要么没开，要么被锁在门外 |
| 6 | **面板 API 一律 403** | 任何脚本化调用都返回 403（补浏览器头也无效）| 自动化验证走不通，白试半天 |
| 7 | **80/443 被上游 DROP** | 安全组放了、服务在听，外面照样超时；**证书全部签不出来** | 证书方案死路，且极易误判为"配置问题" |
| 8 | **`PubkeyAuthentication no` 被镜像写死** | 公钥装好了却始终 `Permission denied (publickey)` | 免密登录失败，自动化断掉 |

还有一条**不是技术问题、但危害最大**的：

| # | 坑 | 后果 |
|---|---|---|
| 0 | **不把教程当清单，凭"能跑通"的目标施工** | 漏掉系统更新、内核调优、认证加固等**不影响即时连通、却决定长期稳定与安全**的步骤 |

## 起源：这个技能为什么存在

一次真实事故：重建一台节点时，AI 助手只盯着"把节点跑通"这个目标施工 ——
节点确实通了，**但漏掉了用户教程里明确写着的「系统更新」「BBR」「2FA」三项**。
结果被用户当场质问：**"教程里明明都有，为什么你还会漏？"**

复盘结论不是"下次注意"，而是**流程缺陷**：

> **有现成教程 / SOP 时，必须把它逐条转成「可勾选清单」再动手，全勾完才算完成。**
> 目标导向（"能连上就行"）一定会漏掉环境准备类步骤。

所以本技能的第一节是**施工纪律**，并且附带 `references/checklist-template.md` 强制落地。

## 目录结构

```
.
├── SKILL.md                          # 技能主体（AI 读这个）
├── references/
│   ├── troubleshooting.md            # 症状 → 根因 → 修法  全量速查表
│   ├── command-recipes.md            # 可直接复制的命令块
│   └── checklist-template.md         # 把教程转成可勾选清单的模板
├── LICENSE
└── README.md
```

## 快速开始

### 方式一：装进支持 Agent Skill 的工具（推荐）

**WorkBuddy / Claude Code 等支持 `SKILL.md` 的工具**：把整个目录放到技能目录即可。

```sh
# 用户级（对所有项目生效）
git clone https://github.com/<你的账号>/vps-node-rebuild-3xui.git \
  ~/.workbuddy/skills/vps-node-rebuild-3xui

# 项目级（仅当前项目）
git clone https://github.com/<你的账号>/vps-node-rebuild-3xui.git \
  <项目目录>/.workbuddy/skills/vps-node-rebuild-3xui
```

之后在对话里提到「重建节点 / 重装 3x-ui / 换机器」等场景，AI 会自动加载。

### 方式二：直接把内容喂给任意 AI

```text
请先读这份技能文档，然后按它来帮我重建节点：
<粘贴 SKILL.md 全文>
```

> 建议**连同 `references/troubleshooting.md` 一起给** —— 那张症状速查表是排障时最省时间的部分。

### 方式三：当人类手册用

`SKILL.md` 本身就是一份结构化的操作手册，`references/command-recipes.md` 里全是可直接复制的命令块。

## 核心方法论（三条，拿走即用）

### 1. 端口状态判据：别把"超时"直接当成"被墙"

| 外测现象 | 含义 |
|---|---|
| **超时** | 包被 **DROP** → 该端口**没通**（安全组放了、服务在听也照样不通）|
| **拒绝（RST）** | 包**到达了主机** → 端口**是通的**，只是没有服务在监听 |
| **OPEN** | 有服务在监听，通的 |

**两个前置纪律**：

1. **必须先让服务在该端口监听，再测** —— 否则分不清"没放行"和"没服务"
2. **本机测端口前，先看路由接口是不是 `utun*`**（`route -n get <IP>`）——
   TUN 会本地接管连接造成**假 OPEN**：连一个不存在的 IP 都"连接成功"

### 2. 验证必须"由外而内"，不能只看进程

"进程在跑 + 端口在听" ≠ "客户端能用"。**真正的验收是：客户端延迟 + 出口 IP 实测。**

同理，BBR 这类内核参数**必须用重启验证持久化** —— 只写 `sysctl.conf` 不写 `modules-load.d`，
重启就失效。

### 3. 放弃证书时的更优解：SSH 隧道

当 80/443 被上游封锁、公开 CA 证书彻底签不出来时，**不要死磕证书**。
把面板改成 **SSH 隧道 + HTTP**：

- 无证书、无警告、**零续期维护**
- 面板**从公网彻底消失**（`ufw delete allow <面板端口>`），只有 SSH 能进 —— **比公开 HTTPS 更安全**
- 做成开机自启 + 断线重连的常驻服务后，用户完全无感

## 兼容性与边界

| 项 | 说明 |
|---|---|
| **3x-ui 版本** | 主要针对 **3.8.x**（引入 `clients` 三表模型）。更早版本客户端直接在 `inbounds.settings` 里，坑 1/2 不适用 |
| **系统** | Ubuntu 22.04+ 实测；Debian 系同理（BBR 模块名一致） |
| **Xray** | 25/26 版 REALITY 注意 ML-KEM 开关（见 `SKILL.md` §10）|
| **不覆盖** | 非 3x-ui 面板（Hiddify / Marzban 等）内部结构不同；端口判定 / BBR / 证书 / SSH 隧道部分仍可参考 |

## 贡献

欢迎提交 Issue / PR。如果你踩到了这里没写的坑，那正是最有价值的补充 ——
请尽量按 **症状 → 根因 → 修法** 的格式描述，这样别的 AI 也能直接消化。

## 免责声明

本项目用于**自有服务器**的部署与故障排查。使用者应遵守其所在地区的法律法规与云服务商条款。
作者不对任何滥用行为负责。

## License

[MIT](LICENSE) © 2026 qixian771-spec
