# 命令速用块（可直接复制）

> 所有 `<尖括号>` 都是占位符，替换成你自己的值。
> 建议**按编号顺序执行**。

## 目录

1. [环境初始化（含系统更新与基础工具）](#1-环境初始化)
2. [开启并持久化 BBR](#2-开启并持久化-bbr)
3. [安装 3x-ui](#3-安装-3x-ui)
4. [补客户端记录（三张表 —— 最容易漏的一步）](#4-补客户端记录三张表)
5. [复位面板账号密码与端口路径](#5-复位面板账号密码与端口路径)
6. [启用 2FA](#6-启用-2fa)
7. [脚本调不通时改读前端 JS](#7-脚本调不通时改读前端-js)
8. [防火墙与安全组](#8-防火墙与安全组)
9. [面板走 SSH 隧道（含 macOS 常驻）](#9-面板走-ssh-隧道)
10. [端口状态判定](#10-端口状态判定)
11. [重启后全面复核](#11-重启后全面复核)

---

## 1. 环境初始化

```sh
export DEBIAN_FRONTEND=noninteractive

# 系统更新（保留现有配置，避免交互卡住）
apt-get update
apt-get full-upgrade -y \
  -o Dpkg::Options::=--force-confdef \
  -o Dpkg::Options::=--force-confold

# 基础工具
apt-get install -y curl wget vim socat ca-certificates lsb-release gnupg ufw

# 时区
timedatectl set-timezone Asia/Shanghai

# 确认更新干净
apt list --upgradable 2>/dev/null | grep -c upgradable     # 期望 0
[ -f /var/run/reboot-required ] && echo "需要重启" || echo "无需重启"
```

---

## 2. 开启并持久化 BBR

```sh
# 加载模块（注意是 tcp_bbr，不是 bbr）
modprobe tcp_bbr

# 确认已可用（必须能看到 bbr）
sysctl -n net.ipv4.tcp_available_congestion_control

# 持久化：模块开机加载 + 内核参数
echo tcp_bbr > /etc/modules-load.d/bbr.conf
grep -q '^net.core.default_qdisc=fq' /etc/sysctl.conf \
  || echo 'net.core.default_qdisc=fq' >> /etc/sysctl.conf
grep -q '^net.ipv4.tcp_congestion_control=bbr' /etc/sysctl.conf \
  || echo 'net.ipv4.tcp_congestion_control=bbr' >> /etc/sysctl.conf
sysctl -p

# 生效确认
sysctl -n net.ipv4.tcp_congestion_control      # 期望 bbr
sysctl -n net.core.default_qdisc               # 期望 fq
```

> **重启后必须再查一次** —— 持久化没配好会在重启后悄悄失效。

---

## 3. 安装 3x-ui

```sh
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)

systemctl is-active x-ui && systemctl is-enabled x-ui
ss -tlnp | grep -E 'x-ui|xray'
```

---

## 4. 补客户端记录（三张表）

**先在面板里建好入站**（拿到入站 ID），或直接写 `inbounds` 表，然后：

```sh
python3 - <<'PY'
import sqlite3, datetime

UUID        = "<你的UUID>"
INBOUND_ID  = 1                    # 入站 ID
EMAIL       = "node-1"
FLOW        = "xtls-rprx-vision"

db = sqlite3.connect("/etc/x-ui/x-ui.db")

def cols(t):
    return [r[1] for r in db.execute(f"pragma table_info({t})")]

def ins(table, data):
    d = {k: v for k, v in data.items() if k in cols(table)}
    sql = f"insert into {table} ({','.join(d)}) values ({','.join('?'*len(d))})"
    db.execute(sql, tuple(d.values()))
    return db.execute("select last_insert_rowid()").fetchone()[0]

now = int(datetime.datetime.now().timestamp() * 1000)

cid = ins("clients", {
    "email": EMAIL, "uuid": UUID, "flow": FLOW, "security": "auto",
    "enable": 1, "tg_id": 0,                      # 必须是整数 0
    "limit_ip": 0, "total_gb": 0, "expiry_time": 0,
    "created_at": now, "updated_at": now,
})

# ★ 关键：flow 靠这一行才会写进生成的配置
ins("client_inbounds", {
    "client_id": cid, "inbound_id": INBOUND_ID,
    "flow_override": FLOW,
})

ins("client_traffics", {
    "client_id": cid, "inbound_id": INBOUND_ID, "enable": 1,
})
db.commit()

print("clients        =", list(db.execute("select id,email,uuid,flow,enable from clients")))
print("client_inbounds=", list(db.execute("select * from client_inbounds")))
PY

systemctl restart x-ui
sleep 5

# 判据：生成的配置里必须有 clients，且必须带 flow
python3 -c "
import json
d = json.load(open('/usr/local/x-ui/bin/config.json'))
for i in d['inbounds']:
    if i.get('protocol') == 'vless':
        print('端口', i.get('port'), '->', json.dumps(i['settings'].get('clients'), ensure_ascii=False))
"
```

**期望输出**：`[{"email": "...", "flow": "xtls-rprx-vision", "id": "..."}]`
**若没有 `flow`** → `client_inbounds.flow_override` 没写对。

---

## 5. 复位面板账号密码与端口路径

```sh
apt-get install -y python3-bcrypt

python3 - <<'PY'
import sqlite3, bcrypt

USERNAME = "<新用户名>"
PASSWORD = "<新密码>"
PORT     = "40786"
BASEPATH = "/<你的路径>/"

db = sqlite3.connect("/etc/x-ui/x-ui.db")

h = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=10)).decode()
db.execute("update users set username=?, password=? where id=1", (USERNAME, h))

def upsert(k, v):
    if db.execute("select count(*) from settings where key=?", (k,)).fetchone()[0]:
        db.execute("update settings set value=? where key=?", (v, k))
    else:
        db.execute("insert into settings(key,value) values(?,?)", (k, v))

upsert("webPort", PORT)
upsert("webBasePath", BASEPATH)
db.commit()

for r in db.execute("select id,username,length(password) from users"):
    print("user:", r)
for r in db.execute("select key,value from settings where key like 'web%'"):
    print(" ", r)
PY

systemctl restart x-ui
```

---

## 6. 启用 2FA

```sh
python3 - <<'PY'
import sqlite3, base64, os

secret = base64.b32encode(os.urandom(20)).decode().rstrip('=')   # 32 字符 base32
db = sqlite3.connect("/etc/x-ui/x-ui.db")

for k, v in (("twoFactorEnable", "true"), ("twoFactorToken", secret)):
    if db.execute("select count(*) from settings where key=?", (k,)).fetchone()[0]:
        db.execute("update settings set value=? where key=?", (v, k))
    else:
        db.execute("insert into settings(key,value) values(?,?)", (k, v))
db.commit()

print("TOTP 密钥 =", secret)
print("otpauth  = otpauth://totp/3x-ui:<用户名>?secret=%s&issuer=3x-ui" % secret)
print("参数     = SHA1 / 6 位 / 30 秒")
PY

systemctl restart x-ui
```

**验证**：浏览器打开面板登录页 —— **出现「动态码」输入框才算成功**。
**兜底（万一登录异常）**：

```sh
python3 -c "import sqlite3;d=sqlite3.connect('/etc/x-ui/x-ui.db');d.execute(\"delete from settings where key like 'twoFactor%'\");d.commit()"
systemctl restart x-ui
```

---

## 7. 脚本调不通时改读前端 JS

```sh
B="http://127.0.0.1:<面板端口>/<webBasePath>"

# 找出登录页引用的 JS
JS=$(curl -s "$B/" | grep -oE 'assets/login-[A-Za-z0-9_-]+\.js' | head -1)
echo "login bundle = $JS"

# ★ 必须用 grep -oE 只输出片段：打包后的 JS 是超长单行
curl -s "$B/$JS" | grep -oE '.{80}(twoFactor|login|password|form).{120}' | head -10
```

**常见收获**：登录接口路径、表单字段名（如 `twoFactorCode`）、2FA 判定接口
（如 `POST /getTwoFactorEnable`）、成功后的跳转逻辑。

---

## 8. 防火墙与安全组

```sh
ufw default deny incoming
ufw default allow outgoing
ufw allow <SSH端口>/tcp
ufw allow <节点端口>/tcp
ufw allow <订阅端口>/tcp
ufw enable
ufw status numbered
```

> **云端安全组必须同步放行**，并**确认「关联实例」指向本机** ——
> 改到未绑定的安全组上等于没改。改完记得点「应用」。

---

## 9. 面板走 SSH 隧道

**服务端：让面板只对 SSH 可见**

```sh
ufw delete allow <面板端口>/tcp                       # 面板从公网消失

python3 -c "import sqlite3;d=sqlite3.connect('/etc/x-ui/x-ui.db');d.execute(\"delete from settings where key in ('webCertFile','webKeyFile')\");d.commit()"
systemctl restart x-ui
```

**客户端（macOS）常驻隧道**

`~/Library/LaunchAgents/com.example.panel-tunnel.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.example.panel-tunnel</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/ssh</string>
    <string>-N</string>
    <string>-o</string><string>BatchMode=yes</string>
    <string>-o</string><string>ExitOnForwardFailure=yes</string>
    <string>-o</string><string>ServerAliveInterval=30</string>
    <string>-o</string><string>ServerAliveCountMax=6</string>
    <string>-o</string><string>ConnectTimeout=15</string>
    <string>-L</string><string>40786:127.0.0.1:<面板端口></string>
    <string><ssh别名></string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardErrorPath</key><string>/tmp/panel-tunnel.err</string>
</dict>
</plist>
```

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.panel-tunnel.plist
launchctl print gui/$(id -u)/com.example.panel-tunnel | grep -E 'state|pid'

# 访问
open http://localhost:40786/<webBasePath>/

# 重建（隧道挂了时）
launchctl kickstart -k gui/$(id -u)/com.example.panel-tunnel
```

> **提醒用户**：始终用 `localhost`，不要混用 `127.0.0.1` —— cookie 不通用会要求重登。

---

## 10. 端口状态判定

```sh
TARGET=<目标IP>
PORT=<端口>

# ① 本机路由接口（若是 utun* 则本机裸连接测试无效）
route -n get $TARGET 2>/dev/null | grep -E 'gateway|interface'

# ② 送一个"必定失败"的对照组 —— 若它也"成功"，说明测法被本地接管污染
python3 - <<PY
import socket
def probe(ip, port, t=5):
    s = socket.socket(); s.settimeout(t)
    try:
        s.connect((ip, port)); return "OPEN"
    except socket.timeout: return "超时"
    except ConnectionRefusedError: return "拒绝(RST)"
    except Exception as e: return type(e).__name__
    finally: s.close()
print("对照 1.2.3.4:443 ->", probe("1.2.3.4", 443))     # 应"超时"；若 OPEN 则测法无效
print(f"目标 $TARGET:$PORT ->", probe("$TARGET", $PORT))
PY
```

**判读**：

| 现象 | 含义 |
|---|---|
| 超时 | 包被 DROP → **没通**（或服务未监听）|
| 拒绝(RST) | 包到达主机 → **通了**，只是没服务 |
| OPEN | 有服务在监听，通的 |

> **被测端口上必须先有服务在监听**，否则测不出"放行"状态。
> 临时监听可用：`systemd-run --unit=t443 --collect python3 -c "..."`（比 `nohup &` 更可靠。

---

## 11. 重启后全面复核

```sh
echo "=== 内核 ==="; uname -r; uptime -p
echo "=== BBR ==="; sysctl -n net.ipv4.tcp_congestion_control; sysctl -n net.core.default_qdisc
echo "=== 待升级 ==="; apt list --upgradable 2>/dev/null | grep -c upgradable
echo "=== 服务 ==="; for s in x-ui ssh ufw fail2ban; do printf "%s=%s " "$s" "$(systemctl is-active $s)"; done; echo
echo "=== 监听 ==="; ss -tlnp | grep -E 'x-ui|xray|sshd'
echo "=== 防火墙 ==="; ufw status | head -1
echo "=== 入站与客户端 ==="; python3 -c "
import sqlite3, json
db = sqlite3.connect('/etc/x-ui/x-ui.db')
for r in db.execute('select id,remark,port,protocol,enable from inbounds'): print(' ', r)
print(' client_inbounds:', list(db.execute('select * from client_inbounds')))
"
```

**再在客户端侧实测**：节点延迟 + **出口 IP**（不能只看端口通不通）。
