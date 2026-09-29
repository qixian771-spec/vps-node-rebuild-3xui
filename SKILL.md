---
name: vps-node-rebuild-3xui
description: 从零重建或迁移一台 3x-ui（x-ui）REALITY 节点时使用——覆盖客户端凭据的三表结构（clients / client_inbounds / client_traffics + flow_override）、面板账号密码的 bcrypt 重置、Ubuntu 上 BBR 的正确开启（tcp_bbr 是模块而非内置）、2FA 的存储位置与验证方式、面板 API 一律 403 时的排障法、80/443 被上游封锁导致证书无解时改用 SSH 隧道访问面板，以及「把教程转成验收清单」的施工纪律。触发场景：重建/重装节点、换机迁移、把原节点配置复制到新机、config.json 里 clients 为空导致认证失败、flow 不生效、BBR 开了没生效、面板 2FA 不确定是否生效、面板登录被拒、面板走 SSH 隧道、复用原节点密钥与 UUID。
license: MIT
---

# 3x-ui REALITY 节点：重建 / 迁移 / 排障

> 这是从一次真实事故里长出来的技能：重建节点时凭"把节点跑通"的目标施工，
> **漏掉了教程里明确写着的「系统更新」「BBR」「2FA」三项**。
> 因此本技能的第一条不是技术，而是纪律。

## 快速定位（先看症状，再跳章节）

| 你遇到的 | 跳到 |
|---|---|
| 要重建/迁移节点，不知从哪下手 | [§0 施工纪律](#§0-施工纪律先做这个) → [§1 环境](#§1-环境初始化) |
| 端口在监听、服务正常，**但客户端认证失败** | [§2 客户端凭据三表](#§2-坑一客户端凭据存三张表不是-inboundssettings) |
| 加了 flow 但还是完全不通 | [§3 flow_override](#§3-坑二flow-来自-client_inboundsflow_override) |
| `lsmod` 查不到 bbr / `modprobe bbr` 报错 | [§4 BBR](#§4-坑三ubuntu-上-bbr-是模块-tcp_bbr) |
| 面板密码忘了 / 要改账号 | [§5 凭据复位](#§5-坑四面板账号密码复位cli-常无修改子命令) |
| 2FA 配了但不确定生效没有 | [§6 2FA](#§6-坑五2fa-存在-settings-表users-表里没有) |
| 面板所有 API 都 403，脚本调不通 | [§7 读前端 JS](#§7-坑六面板-api-一律-403--改读前端-js) |
| 端口外面连不上 / 证书签不出来 | [§8 端口与证书](#§8-坑七八十443-被上游封锁时证书无解--改用-ssh-隧道) |
| 免密 SSH 失败 | [§9 公钥认证](#§9-坑八pubkeyauthentication-被商家镜像写死) |
| 想沿用原节点凭据，让客户端只改 IP | [§10 凭据复用](#§10-凭据复用让客户端只改-ip-和端口) |
| 全部完成，要收尾验收 | [§11 收尾清单](#§11-收尾清单每次都要走) |

配套文件：
- `references/troubleshooting.md` — **症状 → 根因 → 修法** 全量速查表
- `references/command-recipes.md` — 可直接复制的命令块
- `references/checklist-template.md` — 把教程转成可勾选清单的模板

---

## §0 施工纪律（先做这个）

**铁律：凡有用户提供的教程 / SOP，先把它逐条转成「可勾选清单」，再动手。**

只凭"能连上就行"的目标施工，**一定会漏掉环境准备类步骤**（系统更新、内核调优、认证加固），
因为它们不影响"节点能不能通"这个即时目标，却直接决定长期稳定性与安全。

做法：用 `references/checklist-template.md` 把教程灌成表格 → 逐条执行 → **逐条勾选** → **全勾完才算完成**。

---

## §1 环境初始化

```sh
# 1. 系统更新（保留现有配置，避免交互卡住）
apt-get update && apt-get full-upgrade -y \
  -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold

# 2. 基础工具
apt-get install -y curl wget vim socat ca-certificates lsb-release gnupg ufw

# 3. 时区（按用户所在或习惯选择）
timedatectl set-timezone Asia/Shanghai

# 4. BBR（见 §4，注意模块名）
modprobe tcp_bbr
echo tcp_bbr > /etc/modules-load.d/bbr.conf
grep -q '^net.core.default_qdisc=fq' /etc/sysctl.conf || echo 'net.core.default_qdisc=fq' >> /etc/sysctl.conf
grep -q '^net.ipv4.tcp_congestion_control=bbr' /etc/sysctl.conf || echo 'net.ipv4.tcp_congestion_control=bbr' >> /etc/sysctl.conf
sysctl -p && sysctl -n net.ipv4.tcp_congestion_control    # 必须输出 bbr

# 5. 3x-ui
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)

# 6. 防火墙
ufw default deny incoming && ufw default allow outgoing
ufw allow <SSH端口>/tcp && ufw allow <节点端口>/tcp && ufw allow <订阅端口>/tcp
ufw enable
```

> **云控制台的安全组必须同步放行**，并确认**「关联实例」指向本机** ——
> 改到一个未绑定实例的安全组上，等于没改（高频踩坑点）。

---

## §2 坑一：客户端凭据存三张表，不是 `inbounds.settings`

**3x-ui 3.8.x 的客户端模型**：
`clients`（全局客户端）+ `client_inbounds`（关联 + flow 覆盖）+ `client_traffics`（流量统计）。

**症状**：进程起来了、端口在监听、**但客户端认证必失败**。
查运行时配置会看到客户端列表是空的：

```json
"settings": { "clients": [], "decryption": "none", "fallbacks": [] }
```

**原因**：只往 `inbounds` 表插了记录，没建客户端及其关联。

**正确写法**（列名自适应，兼容不同 fork）：

```python
import sqlite3, datetime
db = sqlite3.connect("/etc/x-ui/x-ui.db")
def cols(t): return [r[1] for r in db.execute(f"pragma table_info({t})")]
def ins(table, data):
    d = {k: v for k, v in data.items() if k in cols(table)}
    db.execute(f"insert into {table} ({','.join(d)}) values ({','.join('?'*len(d))})", tuple(d.values()))
    return db.execute("select last_insert_rowid()").fetchone()[0]

now = int(datetime.datetime.now().timestamp() * 1000)
cid = ins("clients", {
    "email": "node-1", "uuid": "<UUID>", "flow": "xtls-rprx-vision",
    "security": "auto", "enable": 1, "tg_id": 0,          # tg_id 必须是整数
    "created_at": now, "updated_at": now,
})
ins("client_inbounds", {"client_id": cid, "inbound_id": <入站ID>,
                        "flow_override": "xtls-rprx-vision"})   # 见 §3
ins("client_traffics", {"client_id": cid, "inbound_id": <入站ID>, "enable": 1})
db.commit()
```

改完 `systemctl restart x-ui`，再查 `bin/config.json` 确认客户端出现。

> `tg_id` 写成字符串会被拒：`json: cannot unmarshal string into Go struct field .0.tgId of type int64`

---

## §3 坑二：`flow` 来自 `client_inbounds.flow_override`

只补 `clients` 表，生成的配置里**没有 `flow` 字段**：

```json
{"email": "node-1", "id": "<UUID>"}          ← 缺 flow
```

而 **Vision 缺 flow = 完全不通**（实测 `http_code=000`）。

必须写 `client_inbounds.flow_override = 'xtls-rprx-vision'`，生成结果才会变成：

```json
{"email": "node-1", "flow": "xtls-rprx-vision", "id": "<UUID>"}
```

**判据**：改完后**一定去读 `bin/config.json`**，肉眼确认 `flow` 在不在。

---

## §4 坑三：Ubuntu 上 BBR 是模块 `tcp_bbr`

| 常见错误查法 | 会误判为 | 正确做法 |
|---|---|---|
| `lsmod \| grep bbr` | 「BBR 不可用」 | `sysctl -n net.ipv4.tcp_available_congestion_control` 看是否含 `bbr` |
| `modprobe bbr` | 「模块不存在」 | **`modprobe tcp_bbr`**（模块名带前缀）|
| 只写 `sysctl.conf` | **重启后失效** | 还要 `echo tcp_bbr > /etc/modules-load.d/bbr.conf` |

**`modprobe tcp_bbr` 报 `Operation not permitted`** =
该实例是**容器或受限虚拟化**，宿主禁止加载内核模块 → **本机无法启用 BBR**，
需服务商开权限或更换机器。**这不是配置问题，不要继续折腾。**

**必须用重启验证持久化**：重启后 `sysctl -n net.ipv4.tcp_congestion_control` 仍输出 `bbr` 才算配好。

**效果参考**：某节点开启后延迟 286ms → 177ms。

---

## §5 坑四：面板账号密码复位（CLI 常无修改子命令）

部分 fork 的 `x-ui` CLI **只有 `settings`（查看）而没有 `setting`（修改）**，
传参只会打印帮助菜单 → 直接改数据库：

```sh
apt-get install -y python3-bcrypt
python3 - <<'EOF'
import sqlite3, bcrypt
h = bcrypt.hashpw(b"<新密码>", bcrypt.gensalt(rounds=10)).decode()
db = sqlite3.connect("/etc/x-ui/x-ui.db")
db.execute("update users set username=?, password=? where id=1", ("<新用户名>", h))
db.commit()
EOF
systemctl restart x-ui
```

密码列存的是 **bcrypt 哈希（60 字符）**；cost 取 10 即可（校验时从哈希内读，不依赖具体 cost）。

面板端口与 Web 路径也在 `settings` 表：`webPort` / `webBasePath`（upsert 后重启生效）：

```python
db.execute("update settings set value=? where key='webPort'", ("<端口>",))
db.execute("update settings set value=? where key='webBasePath'", ("/<路径>/",))
```

---

## §6 坑五：2FA 存在 `settings` 表，`users` 表里没有

- `users` 表只有 `id / username / password / login_epoch` —— **找不到 2FA 字段是正常的**
- 密钥在 **`settings` 表**：`twoFactorEnable` = `true`、`twoFactorToken` = **32 位 base32 密钥**
- **官方判据**：登录页会先请求 `POST /<webBasePath>/getTwoFactorEnable`，
  返回 true 才渲染动态码输入框
- 参数：**SHA1 / 6 位 / 30 秒**；otpauth：
  `otpauth://totp/<issuer>:<user>?secret=<KEY>&issuer=<issuer>`

```sh
python3 - <<'EOF'
import sqlite3, base64, os
s = base64.b32encode(os.urandom(20)).decode().rstrip('=')     # 32 字符 base32
db = sqlite3.connect("/etc/x-ui/x-ui.db")
for k, v in (("twoFactorEnable", "true"), ("twoFactorToken", s)):
    if db.execute("select count(*) from settings where key=?", (k,)).fetchone()[0]:
        db.execute("update settings set value=? where key=?", (v, k))
    else:
        db.execute("insert into settings(key,value) values(?,?)", (k, v))
db.commit(); print("TOTP 密钥 =", s)
EOF
systemctl restart x-ui
```

**⚠️ 锁门风险与兜底**：若密钥格式不被识别 → 登录要码但码永远不对 → **会被锁在外面**。
因此：**动手前必须已确认 SSH 可登录 + 能直连数据库**；
异常时一条命令即可恢复：

```sh
python3 -c "import sqlite3;d=sqlite3.connect('/etc/x-ui/x-ui.db');d.execute(\"delete from settings where key like 'twoFactor%'\");d.commit()"
systemctl restart x-ui
```

**验证方式**：这类 fork 通常**无法用脚本验证**（见 §7），**只能由人在浏览器看登录页是否出现动态码框**。

---

## §7 坑六：面板 API 一律 403 → 改读前端 JS

某些 fork 对**所有脚本化 API 调用**返回 `403`（连匿名的 `/getTwoFactorEnable` 也拦）。
补 `Sec-Fetch-*` / `Origin` / `Referer` / `X-Requested-With` / 浏览器 UA **全部无效**。

**正确姿势：读打包后的前端 bundle** —— 所有客户端逻辑都在里面：

```sh
B="http://127.0.0.1:<面板端口>/<webBasePath>"
JS=$(curl -s "$B/" | grep -oE 'assets/login-[A-Za-z0-9_-]+\.js' | head -1)
curl -s "$B/$JS" | grep -oE '.{80}(twoFactor|login|password).{120}' | head
```

> **务必用 `grep -oE` 只输出匹配片段** —— 打包后的 JS 是**超长单行**，
> 直接输出整行会把终端和上下文撑爆。

从 JS 里通常能直接读出：登录接口路径、表单字段名、是否有 2FA 判定、跳转逻辑等。

---

## §8 坑七/八：80、443 被上游封锁时，证书无解 → 改用 SSH 隧道

### 先学会判端口状态（判据极重要）

| 外测现象 | 含义 |
|---|---|
| **超时** | 包被 DROP → 该端口**没通**（安全组放了、服务在听也照样不通）|
| **拒绝（RST）** | 包**到达了主机** → 端口**是通的**，只是没有服务在监听 |
| **OPEN** | 有服务在监听，通的 |

**两个前置纪律**：
1. **必须先让服务在该端口监听，再测** —— 否则测不出放行状态（无服务时 DROP 与"没放行"表现相同）
2. **本机测端口前必须确认路由接口不是 `utun*`** ——
   TUN 会**在本地接管连接**造成「假 OPEN」（连一个不存在的 IP 都能"连接成功"）。
   检查：`route -n get <目标IP>`，若 interface 是 `utun*`，本机裸连接测试**一律无效**。
   权威做法：用外部 vantage（另一台境外机器）或内核自身的拨号接口测。

### 若 80/443 被上游 DROP

- **HTTP-01（走 80）与 TLS-ALPN-01（走 443）双双不可用 → IP 证书与域名证书都签不出来**
- `acme.sh --standalone` 会**覆盖** `--alpn`（参数优先级）→ 要用 TLS-ALPN 必须**只写 `--alpn` 不带 `--standalone`**
- certbot（Ubuntu 22.04 自带版本）standalone **不支持** `tls-alpn-01`
- acme.sh v3.1.6 已移除 `--yes-I-know-dns-manual-mode-enforce-add-nothing`，
  manual DNS 模式不可用 → **只能走 DNS API 插件**
- **唯一绕开端口封锁的方式：用你自己可控 DNS 的域名走 DNS-01**（不依赖任何端口）
- 另注：Let's Encrypt 的**默认 profile 不允许 IP 标识**，IP 证书需 `--cert-profile shortlived`

### 最优解（比证书更好）：面板改走 SSH 隧道

**收益**：无证书、无警告、零依赖、**面板从公网彻底消失**（只有 SSH 能进）——比公开 HTTPS 更安全。

```sh
# 1. 面板从公网移除
ufw delete allow <面板端口>/tcp

# 2. 面板切回 HTTP（删掉证书设置并重启）
python3 -c "import sqlite3;d=sqlite3.connect('/etc/x-ui/x-ui.db');d.execute(\"delete from settings where key in ('webCertFile','webKeyFile')\");d.commit()"
systemctl restart x-ui
```

**客户端（macOS）做成常驻** —— `~/Library/LaunchAgents/<label>.plist`：

```xml
<key>ProgramArguments</key>
<array>
  <string>/usr/bin/ssh</string>
  <string>-N</string>
  <string>-o</string><string>BatchMode=yes</string>
  <string>-o</string><string>ExitOnForwardFailure=yes</string>
  <string>-o</string><string>ServerAliveInterval=30</string>
  <string>-o</string><string>ServerAliveCountMax=6</string>
  <string>-L</string><string><本地端口>:127.0.0.1:<面板端口></string>
  <string><ssh别名></string>
</array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
```

加载：`launchctl bootstrap gui/$(id -u) <plist路径>`
（重建：`launchctl kickstart -k gui/$(id -u)/<label>`）

访问：`http://localhost:<本地端口>/<webBasePath>/`
—— **HTTP + localhost，永远没有证书警告**。

> **必须提醒用户**：地址**始终用 `localhost`，不要混用 `127.0.0.1`** ——
> 浏览器视为不同站点，cookie 不通用，会莫名其妙要求重新登录。

---

## §9 坑八：`PubkeyAuthentication` 被商家镜像写死

**症状**：公钥已正确装入 `authorized_keys`、权限也对，但 `ssh -o BatchMode=yes` 仍报
`Permission denied (publickey)`。

**排查**：
```sh
grep -iE '^PubkeyAuthentication' /etc/ssh/sshd_config
# 若为 no —— 商家镜像把它关掉了
sed -i 's/^PubkeyAuthentication no/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sshd -t && systemctl restart ssh        # 已建立的会话不受影响
```

**还有一个客户端侧陷阱**：密钥文件名不是默认名（如 `xxx_ed25519`）时，
`ssh host` 不会自动尝试它 —— 必须在 `~/.ssh/config` 里配 `IdentityFile`，或用 `-i` 指定。

---

## §10 凭据复用：让客户端只改 IP 和端口

重建/迁移时**沿用原有的 `UUID` / REALITY `privateKey` / `publicKey` / `shortId`**，
客户端（Clash / mihomo / sing-box 等）就**只需改 `server` 与 `port`**，其余字段一字不动。

**动手前必做：验证密钥对是否匹配**（否则会拿着不配对的公私钥白忙）：

```sh
xray x25519 -i <privateKey>
# 输出的 PublicKey 必须与配置里的 publicKey 完全一致
```

**REALITY 关键参数参考**（照搬教程时注意 SNI 必须与 dest 一致）：
- `dest` / `serverNames`：如 `dl.google.com:443`（需**从该 VPS 实测可访问且支持 TLS 1.3**）
- `shortIds`：随机；`fingerprint`：`chrome`；`spiderX`：留空或 `/`
- 传输：`network = raw`（旧写 `tcp`，同义）；`security = reality`
- **`flow` 必须为 `xtls-rprx-vision`**（客户端侧同样如此）

**客户端侧还有一个高频坑**：mihomo/Clash 连接 **Xray 25/26 新版 REALITY** 时，
若报 `REALITY authentication failed`，而 SNI / 密钥 / shortId 全部正确，
真因是 **mihomo 未启用 X25519+ML-KEM-768 混合密钥交换**，需在节点上加：

```yaml
reality-opts:
  public-key: <pbk>
  short-id: <sid>
  support-x25519mlkem768: true      # 缺这行即认证失败
```

（Xray 客户端会自动协商，所以"用 xray 测是通的、用 mihomo 就不通"，极易误判为节点问题。）

---

## §11 收尾清单（每次都要走）

- [ ] 系统更新完成（`apt list --upgradable 2>/dev/null | grep -c upgradable` = 0）
- [ ] **BBR**：`sysctl -n net.ipv4.tcp_congestion_control` = `bbr`，且**重启后仍为 bbr**
- [ ] 面板：改密码 + **开 2FA**，并确认**登录页出现动态码框**
- [ ] `ufw`：`deny incoming` / `allow outgoing`，只放行必需端口
- [ ] **云控制台安全组同步放行，并确认「关联实例」是本机**
- [ ] 入站：`vless` / `raw` / `reality` / `flow=xtls-rprx-vision` / dest 可从 VPS 实测访问
- [ ] **端到端实测：客户端延迟 + 出口 IP**（不能只看"端口通不通"）
- [ ] 若需长期管理面板：确认 SSH 隧道已常驻且可访问
- [ ] **重启一次并全面复核**（BBR 持久化 / 服务 / 端口 / 节点 / 面板）

---

## 兼容性与边界

| 项 | 说明 |
|---|---|
| 3x-ui 版本 | 主要针对 **3.8.x**（引入 `clients` 三表模型）；更早版本客户端直接在 `inbounds.settings` 里，§2/§3 不适用 |
| 系统 | Ubuntu 22.04+ 实测；Debian 系同理（BBR 模块名一致） |
| Xray | 25/26 版 REALITY 需注意 ML-KEM 开关（见 §10） |
| 不覆盖 | 非 3x-ui 面板（如 Hiddify / Marzban）内部结构不同，仅端口/BBR/证书部分可参考 |

## 免责声明

本技能用于**自有服务器**的部署与故障排查。请遵守你所在地区的法律法规与云服务商条款。
