# 按任务选择的命令块

不是按序全执行的安装脚本。确认版本、实际路径、目标对象、已有授权与备份后，只选本次任务需要的块。示例在目标机执行；`<...>` 必须替换。不要在文档示例中填入真实密码或密钥。

## 1. 只读环境与管理器核对

```sh
uname -r
timedatectl status
sysctl -n net.ipv4.tcp_available_congestion_control
sysctl -n net.ipv4.tcp_congestion_control
sysctl -n net.core.default_qdisc
systemctl is-active x-ui
systemctl is-enabled x-ui
ss -tlnp
ufw status numbered
```

确认 Xray 由 `x-ui` 管理还是独立服务管理，不启动另一套历史 `xray.service` 与现有监听抢端口。服务名、核心路径依实际安装确定。

系统升级/重启仅适用于已纳入范围的部署维护任务。包管理器提示需重启时记录未测项，不为了验收客户端配置自行重启生产机。

## 2. BBR 条件化启用

先用上一节的 sysctl 看 BBR 是否已经可用。需要加载模块时使用 `modprobe tcp_bbr`；若内置或宿主已提供算法，不要求 `lsmod` 出现模块。

在目标机允许、已决定启用 BBR 时，可用专属文件：

```sh
# 模块方案才需要；内置/宿主提供时不执行这一行
printf '%s\n' tcp_bbr > /etc/modules-load.d/node-bbr.conf

printf '%s\n' 'net.core.default_qdisc=fq' 'net.ipv4.tcp_congestion_control=bbr' \
  > /etc/sysctl.d/99-node-bbr.conf
sysctl --system
sysctl -n net.ipv4.tcp_congestion_control
sysctl -n net.core.default_qdisc
```

先检查同名文件及冲突设置；已有内容需备份与有意合并。`sysctl --system` 输出错误不能忽略。安排重启后再验证持久化，未重启则不报告已做重启验收。

## 3. 数据库一致备份与 schema

将 `/etc/x-ui/x-ui.db` 替换成确认过的源路径。下面代码只生成私有快照、输出路径和表结构，不输出行数据或凭据：

```python
from pathlib import Path
import datetime, os, sqlite3

os.umask(0o077)
source = Path('/etc/x-ui/x-ui.db')
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup_dir = Path('/root/node-backups') / stamp
backup_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
target = backup_dir / 'x-ui.db'
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
    for table in ['inbounds', 'clients', 'client_inbounds', 'client_traffics', 'settings']:
        columns = [r[1] for r in src.execute(f'PRAGMA table_info({table})')]
        print(table, columns)
target.chmod(0o600)
print('backup_path', target)
```

## 4. 三表模型与目标 flow 修复

仅在已确认三表模型和目标关联时适用。新增客户端优先走面板/API；直接写库前逐列检查真实约束、外键、已有记录，使用单个事务写完客户端、关联与流量记录。不能通过过滤未知列静默丢弃必需字段，也不能反复 INSERT 生成重复客户端。若缺少 `flow_override`，停止下方示例并查当前 fork 的受支持 API、保存模型或生成代码，再按真实 flow 来源修改唯一目标；不新增猜测列，不盲改全局 flow，也不自行重装。

下面示例只修复**已有目标关联**的 `flow_override`，不会重建客户端或改动其他入站。两个环境变量是已核对的数字记录 ID，不是 UUID：

```python
import os, sqlite3

client_id = int(os.environ['NODE_CLIENT_ID'])
inbound_id = int(os.environ['NODE_INBOUND_ID'])
with sqlite3.connect('/etc/x-ui/x-ui.db') as db:
    columns = {r[1] for r in db.execute('PRAGMA table_info(client_inbounds)')}
    required = {'client_id', 'inbound_id', 'flow_override'}
    if not required <= columns:
        raise RuntimeError('Unsupported client_inbounds schema')
    db.execute('BEGIN IMMEDIATE')
    count = db.execute('SELECT count(*) FROM client_inbounds WHERE client_id=? AND inbound_id=?',
                       (client_id, inbound_id)).fetchone()[0]
    if count != 1:
        raise RuntimeError('Expected exactly one verified target association')
    updated = db.execute('UPDATE client_inbounds SET flow_override=? WHERE client_id=? AND inbound_id=?',
                         ('xtls-rprx-vision', client_id, inbound_id))
    if updated.rowcount != 1:
        raise RuntimeError('Unexpected update count')
print('target_association_updated', True)
```

按已确认管理器重载并读取生成配置。只报告目标 clients 数、flow 一致性和密钥配对结果，不能把整个客户端对象或数据库行打印出来。配置校验通过后还需要真实代理认证与出口测试。

## 5. 面板账号、端口与路径

读取当前 fork 的受支持 CLI/API 和 schema 后，按用户要求修改目标账号。密码由安全输入/受限文件提供，先检查实际哈希格式；禁止在 shell 参数或 heredoc 示例里填真实密码。

端口、base path 与 listen host 的设置键可能因 fork 不同；确认键存在后做事务 update/upsert，不假定用户 ID 为 1。报告字段是否生效，不报告值中的敏感内容。

## 6. 2FA 设置和登录验收

只读查看设置是否启用、密钥格式是否符合当前实现；不要输出密钥或 otpauth URL。按当前面板支持的流程让用户保存密钥并完成验证码录入。

验收包括启用状态、输入框、正确验证码登录。失败先检查服务器时间和 TOTP 算法/位数/步长，不删除 `twoFactor*` 或关闭认证作为自动处理。

## 7. 前端接口定位

仅用于有限次请求纠正后仍无法确定接口约定的情况：

```sh
PANEL_BASE='http://127.0.0.1:<panel-port>/<base-path>'
LOGIN_JS=$(curl --fail --silent --show-error "$PANEL_BASE/" \
  | rg -o 'assets/login-[A-Za-z0-9_-]+\.js' | head -1)
# 必须确认非空、为页面实际资源路径，再请求；只输出匹配片段
curl --fail --silent --show-error "$PANEL_BASE/$LOGIN_JS" \
  | rg -o '.{0,60}(twoFactor|form|login).{0,100}' | head -8
```

bundle 是静态代码证据，不能代替后端状态或成功登录。不要输出整条压缩 JS、会话 cookie 或包含凭据的响应。

## 8. 防火墙与安全组

先确认并放行实际 SSH 端口，保持已有管理连接。在已核对影响的目标规则上修改，然后用 `ufw status numbered`、实际监听和外部访问复核。安全组从实例详情回读协议、端口、源范围、组绑定和保存/应用结果。

不把 `ufw disable` 当默认排障步骤；优先只读检查实际 nftables/iptables 链与抓包。如果已授权的短暂实验确需调整规则，应保存原状态并可靠恢复，不借此建立故障直连路径。

## 9. SSH 隧道管理面板

先按实际配置将面板绑定 loopback，核对主机/云端其他规则与 IPv6；不要仅删除一条 ufw 规则便宣称公网不可达。

```sh
ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=6 \
  -L 127.0.0.1:<local-port>:127.0.0.1:<panel-port> <ssh-alias>
```

用户选择常驻管理时再建立本机服务；重连恢复同一 SSH 目标。验证本地监听只绑定 loopback、隧道失败时不另开公网面板。已有面板 HTTPS 证书不应无条件删除。

## 10. 端口与回落取证

目标机记录监听、指定协议/端口抓包和同窗正常端口对照；外部独立 VPS 发起探测。抓包只记录需要的 TCP 头与时间，不捕捉内容；过滤器、接口、命名空间、时间必须核对。

```sh
# macOS 本机只读路由核对；utun 路径说明本机 connect 可能被代理接管
route -n get <target-ip>

# 在目标 VPS 上验证 REALITY 未认证回落，保持 TLS 校验
openssl s_client -connect 127.0.0.1:<node-port> \
  -servername <reality-sni> -tls1_3 -verify_return_error </dev/null
```

该回落检查不证明 UUID/short ID 正确。`curl --noproxy '*'` 只忽略应用代理环境变量，不能绕过 TUN；不要关闭 TUN 来证明直连。选取自己控制、明确关闭的端口作为负对照，不能把 `1.2.3.4` 等第三方真实地址称为“必定失败”。TEST-NET 地址只用于文档占位，也不是已证明会失败的网络对照。

## 11. 生成配置与重载验收

```sh
<verified-xray-binary> -test -c <generated-config-path>
<verified-mihomo-binary> -t -d <isolated-validation-directory> -f <config-path>
```

通过只是语法/结构可用，还要核对有效管理器、活跃 GUI 订阅和真实出口。Mihomo 离线校验优先独立数据目录与只读地理数据，避免抢生产 cache 锁。

多节点、应用代理与故障验收见 [Clash 路由与 DNS](clash-routing-dns.md)、[Claude 网络保护](claude-network.md)。重启后检查仅在已安排重启时执行；重启未做就保留未测状态。
