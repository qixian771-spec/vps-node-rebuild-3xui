# 排障速查表：症状 → 根因 → 修法

> 用法：先按下表定位症状，再跳到对应修法。
> 每条都标注了 **判据**（怎么确认真的是这个原因），避免"猜着修"。

## 目录

- [A. 节点连不上 / 认证失败](#a-节点连不上--认证失败)
- [B. 面板相关](#b-面板相关)
- [C. 网络与端口](#c-网络与端口)
- [D. 系统与内核](#d-系统与内核)
- [E. 客户端兼容](#e-客户端兼容)
- [F. 测法本身出错（最隐蔽的一类）](#f-测法本身出错最隐蔽的一类)

---

## A. 节点连不上 / 认证失败

| 症状 | 根因 | 判据 | 修法 |
|---|---|---|---|
| 进程正常、端口在听，**客户端认证失败** | 客户端记录只写进 `inbounds` 表，没建 `clients` / `client_inbounds` / `client_traffics` | 读 `bin/config.json` → `settings.clients` 为 `[]` | 补三张表（见 `command-recipes.md` §4）|
| 补了客户端表，**仍然完全不通**（客户端侧 `http_code=000`）| `flow` 缺失 —— 它来自 **`client_inbounds.flow_override`**，不在 `inbounds.settings` 的 JSON 里 | 读 `bin/config.json` → 客户端对象里**没有 `flow` 字段** | `update client_inbounds set flow_override='xtls-rprx-vision'` 后重启 |
| 写入站时报 `tgId` 类型错误 | `clients.tg_id` 必须是**整数** | 报错原文：`cannot unmarshal string into Go struct field .0.tgId of type int64` | 填 `0`，不要填 `""` |
| 服务起不来 / 配置校验失败 | `stream_settings` 或其 JSON 字符串格式错 | `xray-linux-amd64 -test -c bin/config.json` | 用 Python `json.dumps(..., separators=(",",":"))` 生成，别手拼 |
| **完全不通，且没有任何日志** | 可能是 `flow` 或 `security` 不匹配 | 服务端 `openssl s_client -connect 127.0.0.1:<端口> -servername <SNI>` 看是否返回伪装站证书 | 对照 `SKILL.md` §10 逐项核对 |

---

## B. 面板相关

| 症状 | 根因 | 判据 | 修法 |
|---|---|---|---|
| 忘了面板密码 / 要换账号 | 部分 fork 的 CLI **只有 `settings`（查看）没有 `setting`（修改）** | `x-ui setting -username x` 只打印帮助菜单 | 直接改数据库（`command-recipes.md` §5）|
| 改了面板端口/路径不生效 | 该 fork 的 CLI 不支持 | 同上 | 改 `settings` 表的 `webPort` / `webBasePath`（upsert）后重启 |
| **所有 API 调用返回 403** | fork 的防自动化机制 | 连匿名的 `POST /getTwoFactorEnable` 也 403；补 `Sec-Fetch-*`/`Origin`/`Referer`/UA 全部无效 | **不要再试 curl**，改读前端 JS（`command-recipes.md` §7）|
| 登录页看不到动态码输入框 | 2FA 未启用，或密钥写入位置不对 | 前端 JS 会先请求 `/getTwoFactorEnable` | 看 `settings` 表是否有 `twoFactorEnable=true` + `twoFactorToken` |
| **配了 2FA 之后登录一直失败** | 密钥格式不被识别（要码但码永不匹配）| 登录页出现动态码框，但任何码都不通过 | **立即兜底**：删掉 `twoFactor*` 两个键并重启（`SKILL.md` §6）|
| 面板打不开，但 SSH 正常 | 面板端口被公网屏蔽（或被 ufw 移除）| 服务器本地 `curl -sk http://127.0.0.1:<端口>/` 是否 200 | 走 SSH 隧道（`command-recipes.md` §9）|
| `systemctl disable/stop` 报 `Interactive authentication required` | 漏了 `sudo`（polkit 要求交互认证）| 报错原文 | 加 `sudo` |

---

## C. 网络与端口

| 症状 | 根因 | 判据 | 修法 |
|---|---|---|---|
| 从外面连某端口**超时** | 端口**没通**（上游/安全组 DROP），或**服务没在监听** | **必须先让服务监听再测**；有服务仍超时 = 被 DROP | 检查安全组是否放行、**是否关联到本实例** |
| 端口返回**拒绝（RST）** | 端口**是通的**，只是没有服务监听 | RST 说明包已到主机 | 启动服务即可 |
| 安全组改了**没生效** | ① 改到了**未绑定实例**的安全组；② 忘了点「应用」 | 看规则列表的「关联实例」数是否为 0 | 到**实例详情的防火墙页**改，或把安全组绑定到实例 |
| **80/443 一直超时**，配置全对 | 上游/机房层 DROP 这两个端口 | 用外部 vantage 测（非本机）；本机测需确认路由不是 `utun*` | 换非 80/443 端口跑节点；**证书只能走 DNS-01 或放弃** |
| 安全组放行了但还是不通 | 可能是 **ufw** 拦的 | `ufw status` | `ufw allow <端口>/tcp` |
| 端口通了但**节点用不了** | 端口通 ≠ 能认证 | 客户端实测延迟 + 出口 IP | 回到 A 节 |

---

## D. 系统与内核

| 症状 | 根因 | 判据 | 修法 |
|---|---|---|---|
| `lsmod \| grep bbr` **查不到** | Ubuntu 上 BBR 是模块 **`tcp_bbr`**，模块名带前缀；也可能是内置 | `sysctl -n net.ipv4.tcp_available_congestion_control` 是否含 `bbr` | `modprobe tcp_bbr` |
| `modprobe bbr` 报"模块不存在" | 模块名错了 | 同上 | 用 `tcp_bbr` |
| **重启后 BBR 失效** | 只写了 `sysctl.conf`，没配开机加载模块 | 重启后 `sysctl -n net.ipv4.tcp_congestion_control` 变回 `cubic` | `echo tcp_bbr > /etc/modules-load.d/bbr.conf` |
| `modprobe tcp_bbr` 报 **`Operation not permitted`** | 实例是**容器/受限虚拟化**，宿主禁止加载内核模块 | 报错原文；`ls /lib/modules/$(uname -r)/kernel/net/ipv4/` 里**有** `tcp_bbr.ko` 但加载被拒 | **本机无法启用** → 需服务商开权限或换机器，别再折腾 |
| 升级后要求重启 | 内核或 glibc 等已更新 | `cat /var/run/reboot-required` | 择时重启；**注意会中断节点 1–2 分钟** |
| 升级时卡在交互确认 | 配置文件冲突 | 观察到 `*** config file ...` 提示 | 加 `-o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold` 并设 `DEBIAN_FRONTEND=noninteractive` |

---

## E. 客户端兼容

| 症状 | 根因 | 判据 | 修法 |
|---|---|---|---|
| **`REALITY authentication failed`**，但 SNI / 密钥 / shortId 全对 | **mihomo/Clash 未启用 X25519+ML-KEM-768 混合密钥交换**（服务端是 Xray 25/26 新版 REALITY）| **同一配置用 xray 客户端测是通的，mihomo 不通** | 在节点 `reality-opts` 加 `support-x25519mlkem768: true` |
| 客户端延迟正常但**打开网站超时** | 可能是**本地 DNS 污染**被传给了节点 | 对比：命中 `MATCH`（走代理）的站点通、命中域名规则的站点不通 | 把本地 DNS 改成 `fake-ip` 模式，让域名交给节点侧解析 |
| 一直连不上某节点，其他节点正常 | 分组指向不一致 | 查 mihomo 各代理组当前 `now` 是否都指向可用节点 | 逐个组切到可用节点；**重启客户端后分组选择可能回落到组内第一项** |
| 客户端延迟测试失败但实际能用 | 测试 URL 或超时参数不合适 | 换 `url=http://www.gstatic.com/generate_204` 重测 | — |

---

## F. 测法本身出错（最隐蔽的一类）

> **这一节的教训最贵：错误的测法会给出"成功"的假象，让你得出完全相反的结论。**

| 假象 | 成因 | 如何识别 | 正确做法 |
|---|---|---|---|
| **本机测任意 IP 端口都"OPEN"** | **TUN 模式在本地接管连接**（`connect()` 立即返回，后台才拨号）| 拿一个**不存在的 IP**（如 `1.2.3.4:443`）做对照 —— **如果它也"成功"，测法已被污染** | 先 `route -n get <目标IP>` 看接口；若是 `utun*`，改用外部 vantage 或内核自身拨号接口测 |
| 直连一个被封锁的 IP 显示"出口 IP 正常" | 同上（流量被 TUN 接管后走了代理）| 用 `curl --noproxy '*'` 取出口 IP —— 若结果等于代理出口，说明已被接管 | 同上 |
| 端口"通"但服务明明没起 | 上述假 OPEN | 对照组测试 | 同上 |
| 用 `/delay` 数值与 `curl` 端到端耗时互相比较 | **两者口径不同**（delay 不含本地到代理的建连与 DNS）| 同一节点两种测法数值差很大 | 横向比较时**统一口径**；对客户端体验而言以端到端为准 |
| **重启后没验证就宣布完成** | 内核参数/模块加载未持久化 | 重启后复查 | 关键项（BBR、服务、端口、节点）**重启后必须复核** |

### 通用纪律

> **给出任何结论之前，先问一句：这个测法会不会被本地接管或污染？**
> **并且永远配一个"必定失败"的对照组。**

---

## 附：一次性全面体检脚本

```sh
# 在服务器上执行，输出一份状态快照
echo "=== 系统 ==="; uname -r; uptime -p
echo "=== 内核调优 ==="; sysctl -n net.ipv4.tcp_congestion_control; sysctl -n net.core.default_qdisc
echo "=== 待升级 ==="; apt list --upgradable 2>/dev/null | grep -c upgradable
echo "=== 服务 ==="; for s in x-ui ssh ufw fail2ban; do printf "%s=%s " "$s" "$(systemctl is-active $s)"; done; echo
echo "=== 监听 ==="; ss -tlnp | grep -E 'x-ui|xray|sshd'
echo "=== 防火墙 ==="; ufw status
echo "=== 入站 ==="; python3 -c "
import sqlite3;db=sqlite3.connect('/etc/x-ui/x-ui.db')
for r in db.execute('select id,remark,port,protocol,enable from inbounds'): print(' ',r)
print(' client_inbounds:', list(db.execute('select * from client_inbounds')))
"
```
