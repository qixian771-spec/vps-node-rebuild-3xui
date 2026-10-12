# Clash 多节点手动出口、DNS 与故障验收

适用于“国内直连，国外全部使用 GUI 当前选择的自建节点；节点失效时失败，不自动换节点或直连”的要求。参考实测版本为 [Mihomo v1.19.29](https://github.com/MetaCubeX/mihomo/releases/tag/v1.19.29) 和 [Clash Verge Rev v2.5.2](https://github.com/clash-verge-rev/clash-verge-rev/releases/tag/v2.5.2)。升级后重新核对配置生成、DNS 策略和连接复用行为，不把这两个版本当作永久推荐版本。

日期、实测版本与抓包案例均来自 **2026-09-30 的参考案例**；它们不是当前任务的 `active/pass` 证据，需要按下文重新验收。

## 1. 出口与规则不变量

- 只有一个用户可选的 `select` 出口组，成员与用户要求一致；下文三节点仅为示例，增加第四个节点不应改变分流与故障行为。
- 出口组禁止 `DIRECT`、`fallback`、`url-test`、`load-balance` 或套入这些自动组。DNS 也不设置 `fallback` / `fallback-filter`。
- 显式定义 `GLOBAL`，成员只有 `出口选择`，并设 `hidden: true`。不要让自动生成的 GLOBAL 提供独立节点或 DIRECT 选项；全局模式也必须保留同一个选择。
- 规则顺序：显式国外保护域名 → private → 国内 GEOSITE → 国外 GEOSITE → 国内 GEOIP → `MATCH,出口选择`。国外 GEOSITE 应在 `GEOIP,CN` 前，否则某些国外域名的 CDN IP 会被归入直连。
- 要求立即统一出口时，切换后关闭旧连接。改变 selector 不代表既存 TCP / WebSocket / DoH 连接已迁移；完成统一出口需要新建连接。按用户授权的出口切换范围执行并说明会话将中断，不清理无关 core 的连接。

Claude 等关键服务的核心域名应在所有 CN / GEOIP 规则之前显式保护。Claude 当前官方桌面列表可由六个后缀覆盖：`anthropic.com`、`claude.ai`、`claude.com`、`claude.app`、`claudeusercontent.com`、`claudemcpcontent.com`。当前 CLI 文档另列 Datadog 的两个精确主机：`http-intake.logs.us5.datadoghq.com`、`browser-intake-us5-datadoghq.com`。规则与 DNS 策略均需覆盖。[官方 Desktop 网络要求](https://code.claude.com/docs/en/desktop#network-access-requirements)、[当前 CLI 网络配置](https://code.claude.com/docs/en/network-config)。

Sentry / Statsig 域名只能标注为兼容保护，不能说当前 CLI 必然使用它们。需要时将已核实的域名、安装资产、字体/CDN 和自定义 MCP / OTLP / 网关端点加入同一优先区域；不要套用过时的网络白名单。应用专属代理与域名维护见 [Claude 网络保护](claude-network.md)。

## 2. DNS 优先级与生成配置

**普通域名策略并不天然优先于 geosite。** v1.19.29 的 `parseNameServerPolicy` 保留 YAML 键顺序；`NewResolver` 将相邻普通域名组成 trie 块，遇到 geosite / rule-set matcher 就按原位置插入；`matchPolicy` 返回首个匹配块。因此，显式保护域名的 `nameserver-policy` 必须写在 `geosite:cn` / private 策略之前。[配置解析源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.29/config/config.go)、[resolver 源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.29/dns/resolver.go)。

`fake-ip-filter: geosite:cn` 只决定返回真实 IP 还是 fake IP。命中跳过 fake IP 后，查询仍进入 resolver 的 nameserver-policy；真实 IP 响应也会建立域名映射。它不会自己选择国内 DNS。已有正确的显式 DNS 和路由优先级时，不必仅为 DNS 出口目的改整个 fake-ip-filter。域名未知、缓存映射冲突、应用自行解析的流量仍需另外验收。[DNS middleware 源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.29/dns/middleware.go)。

DNS 角色必须分开：

| 字段 | 本模式的职责 |
|---|---|
| `nameserver`、国外域名 policy | 使用带字面 IP 的公共 DoH，显式 `#出口选择` |
| 国内域名 policy、`direct-nameserver` | 国内 DoH，显式 `#DIRECT` |
| private 域名 policy | 明确信任的 LAN DNS `#DIRECT`、本地 hosts 或明确拒绝 |
| `default-nameserver` | DNS 服务器域名的 bootstrap；地址必须是字面 IP |
| `proxy-server-nameserver` | 仅解析节点服务器域名，不是国外业务域名的 DNS |

例如公共解析器用 `https://1.1.1.1/dns-query#出口选择`，避免为 `cloudflare-dns.com` 先走国内 bootstrap 查询。若节点 `server` 本身是域名，仍需审计它的 bootstrap；已有可信地址时可让 `server` 使用 IP，TLS `servername` / Trojan `sni` 保留正确域名。不要混淆连接地址与证书校验名。`direct-nameserver` 默认不遵守 nameserver-policy；需要 DIRECT 保留 private 等指定策略时，设置 `direct-nameserver-follow-policy: true`。关键服务仍必须先被显式路由到代理。[DNS 字段说明](https://wiki.metacubex.one/config/dns/)。

不要把 `geosite:private` 交给公共 DNS：它包含 `.lan`、`.local`、`.internal`、`.home.arpa` 和私网反向区，可能暴露内部名称并失去 LAN 答案。private policy 放在 CN 前。模板的 `192.0.2.53` 也是文档占位，必须换成实际可信的 LAN DNS；若没有这种解析需求，用本地 hosts 或 `rcode://name_error` 明确拒绝，不发送到公共解析器。[官方 private 集合](https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/private.list)。

Clash Verge 会从 profile、全局扩展、专属脚本、GUI DNS/TUN 覆写生成运行配置。**只修改 `clash-verge.yaml` 不构成持久化修复。**

1. 保存可维护的源配置，更新真正选中的 profile。
2. 审计全部扩展顺序。确有 GUI 合并冲突时，专属 profile 脚本应整体赋值 `config.dns`，使未出现在源配置里的旧字段不能残留；删除旧 `fallback` / `fallback-filter` 和非预期 `prepend-rules`。不要只覆盖 nameserver 而留下旧 policy。
3. 通过 GUI 重新激活生成配置。核对源、持久 profile、生成配置中的 DNS / 规则 / 组成员一致。
4. 通过当前 core API 核对版本、规则顺序、selector 当前值、GLOBAL 和 TUN；API 不暴露 DNS 时，明确说明 DNS 证据来自生成配置，再用实际查询与远端 metadata 补证。
5. 再次重新加载，重复关键检查，确认默认选择被保存。不要用手改生成文件代替此步骤。

专属脚本仅在需要覆盖合并行为时增加，不应顺手改写无关订阅。API secret、节点 UUID、密码、私钥、shortId 不进入文档或普通日志。

## 3. 去敏结构模板

下面是结构示例，**不能原样部署**。三个节点地址属于文档保留网段；替换全部 `REPLACE_*`、TLS 名和节点参数，再做 core 配置检查与认证测试。Mihomo 的客户端 `network: tcp` 可对应 Xray 的服务端 RAW 传输，不能机械复制字段名。

```yaml
mixed-port: 7890
allow-lan: false
mode: rule
ipv6: false
profile:
  store-selected: true
  store-fake-ip: true

proxies:
  - {name: 节点A, type: vless, server: 203.0.113.10, port: 8443,
     uuid: REPLACE_UUID_A, network: tcp, tls: true,
     servername: reality.example.com, flow: xtls-rprx-vision,
     client-fingerprint: chrome, udp: true,
     reality-opts: {public-key: REPLACE_PUBLIC_KEY_A, short-id: REPLACE_SHORT_ID_A}}
  - {name: 节点B, type: vless, server: 198.51.100.20, port: 443,
     uuid: REPLACE_UUID_B, network: tcp, tls: true,
     servername: reality.example.com, flow: xtls-rprx-vision,
     client-fingerprint: chrome, udp: true,
     reality-opts: {public-key: REPLACE_PUBLIC_KEY_B, short-id: REPLACE_SHORT_ID_B}}
  - {name: 节点C, type: trojan, server: 192.0.2.30, port: 443,
     password: REPLACE_TROJAN_PASSWORD, sni: trojan.example.com,
     skip-cert-verify: false, udp: true}

proxy-groups:
  - {name: 出口选择, type: select, proxies: [节点A, 节点B, 节点C]}
  - {name: GLOBAL, type: select, hidden: true, proxies: [出口选择]}

dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  fake-ip-filter: [geosite:cn, geosite:private, '+.lan', '+.local']
  respect-rules: false
  default-nameserver: ['https://223.5.5.5/dns-query#DIRECT']
  nameserver: ['https://1.1.1.1/dns-query#出口选择']
  proxy-server-nameserver: ['https://223.5.5.5/dns-query#DIRECT']
  direct-nameserver: ['https://223.5.5.5/dns-query#DIRECT']
  direct-nameserver-follow-policy: true
  nameserver-policy:
    '+.anthropic.com': ['https://1.1.1.1/dns-query#出口选择']
    '+.claude.ai': ['https://1.1.1.1/dns-query#出口选择']
    '+.claude.com': ['https://1.1.1.1/dns-query#出口选择']
    '+.claude.app': ['https://1.1.1.1/dns-query#出口选择']
    '+.claudeusercontent.com': ['https://1.1.1.1/dns-query#出口选择']
    '+.claudemcpcontent.com': ['https://1.1.1.1/dns-query#出口选择']
    http-intake.logs.us5.datadoghq.com: ['https://1.1.1.1/dns-query#出口选择']
    browser-intake-us5-datadoghq.com: ['https://1.1.1.1/dns-query#出口选择']
    cloudflare-dns.com: ['https://1.1.1.1/dns-query#出口选择']
    geosite:private: ['192.0.2.53#DIRECT']  # 替换为可信 LAN DNS，或用 rcode://name_error
    geosite:cn: ['https://223.5.5.5/dns-query#DIRECT']

tun:
  enable: true
  stack: gvisor
  auto-route: true
  auto-detect-interface: true
  dns-hijack: [any:53, 'tcp://any:53']

rules:
  - DOMAIN-SUFFIX,anthropic.com,出口选择
  - DOMAIN-SUFFIX,claude.ai,出口选择
  - DOMAIN-SUFFIX,claude.com,出口选择
  - DOMAIN-SUFFIX,claude.app,出口选择
  - DOMAIN-SUFFIX,claudeusercontent.com,出口选择
  - DOMAIN-SUFFIX,claudemcpcontent.com,出口选择
  - DOMAIN,http-intake.logs.us5.datadoghq.com,出口选择
  - DOMAIN,browser-intake-us5-datadoghq.com,出口选择
  - DOMAIN,cloudflare-dns.com,出口选择
  - GEOSITE,private,DIRECT
  - GEOIP,private,DIRECT,no-resolve
  - GEOSITE,CN,DIRECT
  - GEOSITE,geolocation-!cn,出口选择
  - GEOIP,CN,DIRECT
  - MATCH,出口选择
```

已存在 Trojan 服务时，用原生 Trojan 节点直接连服务端，验证证书及 hostname，开启并实测 UDP。不要把 `127.0.0.1:1082` 等临时本地 SOCKS 包装器当作节点服务器；它依赖另一个常驻进程，也可能没有 SOCKS UDP 支持。

## 4. TUN、IPv6 与嗅探边界

TUN 要分别接管 UDP 53 和 TCP 53，不能只测 UDP DNS。macOS 对发往 LAN DNS 地址的自动劫持有平台限制；检查 `scutil --dns`、实际 UDP/TCP 请求和路由，而不是看到 `dns-hijack` 就宣布系统 DNS 全覆盖。必要时按用户授权调整系统 DNS 与路由，并验证 Clash 启停行为。[官方 TUN 说明](https://wiki.metacubex.one/config/inbound/tun/)。

需要本地 DNS 入口、Chrome/Safari WebRTC 或系统防绕行时，继续读 [Mac 防泄露](macos-leak-guard.md)。其中的 UID 级防火墙影响该用户的其他应用，不能因普通 VPS 部署而自动启用；`127.0.0.1:1053` 也不能直接作为不支持端口的系统 DNS 地址。

`ipv6: false` / `dns.ipv6: false` 不等于操作系统没有公网 IPv6 出口。检查实际全局 IPv6 地址、默认路由以及原生 IPv6 HTTPS 行为；有可用 IPv6 时，验证它经当前节点或明确失败。没有可用 IPv6 环境时，标记未覆盖，而不是宣称未来 IPv6 不会泄漏。

SNI 嗅探可能让端口测试误判：向节点 IP 发 TLS 握手、SNI 填 REALITY 伪装域名时，嗅探可能按 SNI 分流，若启用 destination override 还可能改连伪装站。因此，证书返回正确不能单独证明节点 IP:port 可达。按范围排除被测节点 IP、核对 `parse-pure-ip` / `override-destination`，或使用 core 拨号/外部 vantage 验证；不要为了测试直连关闭用户正在依赖的 TUN。`override-destination: false` 也不代表嗅探结果完全不参与规则匹配。[官方嗅探字段](https://wiki.metacubex.one/config/sniff/)。

## 5. 每个 GUI 选择都验收

| 检查 | 必须观察到 |
|---|---|
| GUI 切换与 API | 当前 selector 为指定节点，重载后默认值符合要求 |
| 显式 HTTP/SOCKS 代理 | 两个独立 IP 查询服务返回该节点的实际出口 |
| 原生请求经 TUN | 不显式指定代理，出口仍是同一节点；核对真实路由与 core 连接证据 |
| SOCKS UDP（要求支持时） | UDP ASSOCIATE + 实际 DNS 往返成功，不能用 TCP HTTPS 替代；未支持/未验证的节点显式禁用 UDP，不能另选出口处理 |
| 国内 DIRECT | 国内业务/解析在 DIRECT 链上，仍保留 TUN |
| 内置国外 DNS | 独特 nonce 查询确实触发上游；远端 metadata 对应当前节点 |

节点 IP 与公网出口 IP 可能不同。先实测建立预期，不因交接文档、节点名称或教程推荐就认定出口。连接缓存、DNS 缓存及旧 DoH keep-alive 可能掩盖问题；切换验收须用新连接、唯一查询名并核对选择。

### 短请求通过，不等于 GPT/Claude 长连接通过

区分四项：TCP 可达、代理认证、实际出口、应用持续会话。GUI 延迟和两个 IP 查询只能支持其中相应部分；SOCKS 节点可用于 HTTPS 并不说明其本身具备 TLS 隧道或 UDP 支持，不把它描述成与 REALITY 完全相同。

关闭旧连接可让新业务使用新 selector，同时会中断现有 WebSocket/SSE。切换瞬间的短暂重连与随后数分钟持续重试分开记录。用户反馈 GPT 一直重连时，核对切换时间、同一应用的连接关闭/打开/重试耗尽事件、测试窗口长度与恢复原节点后的表现；不要读取聊天内容、导出令牌或把日志条数当成独立故障次数。不同远程主机的 SSH/应用服务器重连不应混入 GPT 专用连接统计。

有授权才实际切换或用应用登录会话测试，不替用户发起聊天。否则用隔离核心做有限诊断并将生产会话标未测。持续重连应保留应用验收未通过/原因未确认；IP 查询成功不能覆盖这个结果。恢复原默认节点属于明确的人工收尾，与故障时自动换节点不同。没有用户切换授权就保持原节点，不通过新增自动组、直连或另一代理链掩盖问题。

### 不自动换出口的故障测试

只在隔离 core 内做。使用独立目录、监听端口、API、缓存，关闭该 core 的 TUN/系统代理；不得使测试核接管生产流量。保持其他节点完整存在，将**已选节点**的连接地址改成 `127.0.0.1:1`，先确认本机该端口没有监听，再验证：

- selector 始终保持原选择；规则模式和 GLOBAL 都不能自动换节点或 DIRECT。
- 多个国外 HTTPS 请求与独特的国外 DoH 查询失败。
- 国内 DIRECT DNS 仍能成功，证明失败是选中出口不可用，而非整个测试进程失效。
- 不能拿任意真实公网地址（例如 `1.2.3.4`）称作“必定不可达”。文档保留地址也不是主动拒绝连接的等价物。

测试代码的 `finally` 必须终止自己创建的隔离 core、子进程和捕获并确认退出；不得模糊匹配或终止用户连接、生产 core。

## 6. DoH 远端 metadata 证据

在三台节点上并行限定捕获“指定解析器 IP 的 TCP 443”，只记录时间、方向和 TCP length。先确认工具已存在，不为了验收安装服务。不要 `-A` / `-X`，不保存 payload 或无关流量。

**仅禁止打印 payload 不等于没有捕获 payload。** snaplen 必须根据实际链路类型和协议计算、验证。此次 Linux `any` 强制 `LINUX_SLL2` 时，20 字节 cooked header + IPv4 最小 20 字节头 + TCP 最小 20 字节头，使 `-s 60` 截断在 payload 之前；TCP/IP options 会减少可见 TCP 头长度，不会增加 payload。不能把这个值照搬到 Ethernet、IPv6、隧道或其它链路类型。若无法确定头边界，改用可提供连接计数的工具或只交付不确定结论。

执行要在**同一编排**中完成：

1. 准备三条 SSH 会话，测量新的时间偏移。每次记录本机 send、远端 clock、本机 receive；远端相对本机的偏移落在 `[server-receive, server-send]`。保留上下界，不强行假定网络对称。
2. 三机同时启动有自动结束期限的捕获，确认各自 stderr 已显示监听。
3. 立即由同一编排向生产 DNS API 发唯一 nonce 的查询，记录每次本机 start/end。不要依赖父子任务 READY 消息往返后再发探针；短窗口可能早已结束。
4. 用偏移上下界校正查询窗口，确认它完整落在捕获窗口内。当前节点在校正窗口有 TLS 业务数据，其他节点无对应数据；记录背景流量与不确定度。
5. 等待有界捕获退出；异常时只停止本任务明确记录的 PID/进程组，在 `finally` 确认所有捕获停止。

ACK / SYN / FIN 的零长度包不能证明 DNS；少量 TLS 数据也可能只是心跳或关闭等控制流量，例如一次错过探针窗口的捕获只有两个 39-byte 数据包，不能单独认作查询证据。探针错过捕获窗口必须标记 inconclusive，不能以“有 TLS 字节”补判成功。唯一查询名、API 返回、校正时间和业务字节共同支持路径结论；metadata 不解密 DNS，也不证明日后所有查询路径。

## 7. 对用户说明的隐私范围

本模式保证范围是：**经过当前生产 core 的已覆盖国外业务与其 DNS，在选定节点不可达时失败，不自动换节点/直连**。国内 DIRECT 是用户明确选择的行为。没有独立 OS 防火墙/kill switch 时，不能保证 Clash 退出、TUN 关闭或用户切到直接模式后仍防止直连泄漏。

不要为验证直连关闭正在保护会话的 TUN；使用 core DIRECT 路径、连接证据和受控测试。应用专属 HTTP 代理可减少部分绕行，但不能替代系统防火墙，也不能证明所有子进程、自定义端点或旧会话采用了它。

DoH 加密传输不等于匿名：递归解析器可见查询域名和连接来源；经节点的 DoH 来源通常为节点出口。权威 DNS 通常看到递归解析器来源，ECS 则可能携带客户端子网；Cloudflare 当前不向权威发送 ECS，特定诊断域名除外。直接 HTTPS 服务可见到达它的出口 IP，并仍可关联账号和应用数据。代理服务端若自行解析目标域名，其 DNS 必须另外审计，客户端 DoH 捕获不能证明全部服务端 DNS 使用同一解析器。[RFC 8484](https://www.rfc-editor.org/rfc/rfc8484)、[RFC 7871](https://www.rfc-editor.org/rfc/rfc7871)、[Cloudflare ECS FAQ](https://developers.cloudflare.com/1.1.1.1/faq/)。

结论只陈述实测路径与配置边界，不推测服务风控，不承诺“100% 安全”“永不泄漏”或“不会封号”。
