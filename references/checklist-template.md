# 教程对照检查清单（模板）

> **用法**：把用户给的教程 / SOP 逐条填进下表。**动手前先填，完成后逐条勾选，全勾完才算完成。**
>
> **为什么必须这么做**：只凭"把节点跑通"的目标施工，**一定会漏掉环境准备类步骤**——
> 因为它们不影响"节点能不能通"这个即时目标，却直接决定长期稳定性与安全。
> 这不是"下次注意"能解决的，是流程问题。

**教程来源**：
**目标机器**：
**开工时间**：
**完成时间**：

---

## 一、底层环境准备

| # | 步骤 | 命令 / 要求 | 状态 |
|---|---|---|---|
| 1.1 | 更新系统 | `apt-get update && apt-get full-upgrade -y` | ⬜ |
| 1.2 | 基础工具 | `curl wget vim socat ca-certificates lsb-release gnupg ufw` | ⬜ |
| 1.3 | 设置时区 | `timedatectl set-timezone <TZ>` | ⬜ |
| 1.4 | **开启 BBR** | `modprobe tcp_bbr` + `modules-load.d` + `sysctl.conf` | ⬜ |

## 二、面板安装与加固

| # | 步骤 | 要求 | 状态 |
|---|---|---|---|
| 2.1 | 安装面板 | 官方脚本 | ⬜ |
| 2.2 | 记录账号 / 密码 / 端口 | — | ⬜ |
| 2.3 | 面板端口避开 80 / 443 / 8080 | — | ⬜ |
| 2.4 | ufw 默认策略 | `deny incoming` / `allow outgoing` | ⬜ |
| 2.5 | ufw 放行端口 | SSH / 节点 / 面板 / 订阅 | ⬜ |
| 2.6 | **云安全组同步放行** | 并确认**「关联实例」是本机** | ⬜ |
| 2.7 | 排查订阅端口 | `ss -tlnp` / 日志中的 `Sub server` | ⬜ |
| 2.8 | 改面板密码 | — | ⬜ |
| 2.9 | **开启 2FA** | **登录页出现动态码输入框才算成** | ⬜ |

## 三、入站配置

| # | 步骤 | 要求 | 状态 |
|---|---|---|---|
| 3.1 | 基础设置 | 协议 / 监听 IP 留空 / 端口 / UUID / Email | ⬜ |
| 3.2 | **Flow** | `xtls-rprx-vision`（缺它完全不通）| ⬜ |
| 3.3 | 传输设置 | 网络 `tcp`/`raw`、安全 `reality` | ⬜ |
| 3.4 | **客户端记录三表** | `clients` + `client_inbounds` + `client_traffics` | ⬜ |

## 四、REALITY 参数

| # | 步骤 | 要求 | 状态 |
|---|---|---|---|
| 4.1 | dest / serverNames | 两者一致（如 `dl.google.com:443`）| ⬜ |
| 4.2 | privateKey | X25519；用 `xray x25519 -i` 验证与 publicKey 匹配 | ⬜ |
| 4.3 | shortIds / fingerprint / spiderX | 随机 / `chrome` / 留空或 `/` | ⬜ |
| 4.4 | 目标站可访问性 | **从该 VPS 实测**支持 TLS 1.3 且证书与 SNI 匹配 | ⬜ |

## 五、客户端与验收

| # | 步骤 | 状态 |
|---|---|---|
| 5.1 | 保存入站 → 重启核心 | ⬜ |
| 5.2 | 导入客户端 → 核对 7 项（security / network / flow / SNI / pbk / sid / fingerprint）| ⬜ |
| 5.3 | **端到端实测延迟 + 出口 IP**（不能只看端口通不通）| ⬜ |
| 5.4 | 若面板有 2FA：**浏览器实测能否用动态码登录** | ⬜ |
| 5.5 | **重启一次并复核**（BBR 是否持久 / 服务 / 端口 / 节点 / 面板）| ⬜ |

---

## ⚠️ 「教程里有、照抄会踩坑」的点（模板通用）

1. **BBR 的检查命令**
   教程常写 `lsmod | grep bbr` —— **在 Ubuntu 上会误判**。
   BBR 是模块 **`tcp_bbr`**：
   ```sh
   modprobe tcp_bbr                                    # 不是 modprobe bbr
   sysctl -n net.ipv4.tcp_available_congestion_control # 看上没上
   echo tcp_bbr > /etc/modules-load.d/bbr.conf         # 否则重启失效
   ```

2. **ufw 放行 80/443 ≠ 真的能用**
   这两个端口常被机房 / 上游层 DROP，导致公开 CA 证书（HTTP-01 走 80、TLS-ALPN-01 走 443）**全部签不出来**。
   **测端口前必须先让服务在监听，并确认本机路由接口不是 `utun*`**（TUN 会造成假 OPEN）。

3. **面板能在浏览器打开 ≠ 配置正确**
   真正的验收是**客户端延迟 + 出口 IP 实测**。
