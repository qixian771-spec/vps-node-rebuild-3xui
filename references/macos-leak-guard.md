# Mac DNS、WebRTC 与浏览器防绕行

仅在用户要求客户端防泄露时执行。单纯新建 VPS、只查询 IP 或只比较节点，不扩展成系统防火墙任务。先完成 [Clash 单一手动出口与 DNS](clash-routing-dns.md)。本文提供 2026-10-11 的经验和可复用施工步骤；历史通过不算下一台机器的验收结果。

## 1. 先明确作用范围与参数

| 层 | 配置意图 | 不能替代的验证 |
|---|---|---|
| Clash DNS | 国外及保护域名 DoH 经手动 selector；国内 DoH DIRECT | 系统解析器、浏览器独立 DNS、服务端解析 |
| 浏览器 | 限制 WebRTC 的非代理路径 | 其他浏览器、Electron、手机、任意进程 |
| PF 端口规则 | 阻断物理出口 53/853 与常见 STUN/TURN | 任意 443 DoH、任意端口 WebRTC |
| 可选 UID 级 PF | 当前用户的新公网 TCP/UDP 先进入 TUN/本地代理 | root/其他 UID、已有状态、代理核心自身的错误分流 |

记录默认浏览器、所有请求保护的浏览器版本、当前 selector 与实际出口、系统 HTTP/SOCKS/PAC、当前网络服务的 DNS、TUN 接口、核心与浏览器网络进程 UID、现有 PF anchor/状态及启动方式。只读相关配置，不读取浏览历史、账号或聊天。

UID 级限制作用于该用户的其他应用，启用前说明影响并核对用户已授权的范围；不要把它悄悄包装成 Safari 专属选项。核心若与被拦用户同 UID，模板会把核心出口也拦住：停止套用该模板，重新设计并验证身份/进程隔离，不能用放行该 UID 的所有流量来“修好”。

备份源 profile、专属脚本、生成配置、相关浏览器策略键、每个拟改网络服务的原 DNS（区分 DHCP/空列表与手填）、PF 文件及本次新增文件清单。私有目录 `0700`、凭据和备份 `0600`。记录人工撤销步骤；不要设置遇到失败就自动关闭保护或换公网 DNS。

## 2. 系统 DNS 接入受保护的解析路径

先确认客户端是否管理系统 DNS。支持稳定使用 loopback 时，采用下列本地解析入口；Clash Verge 在 macOS fake-IP/TUN 下可能覆写系统 DNS，需同时执行本节末尾的启动验收，不能只反复手工改地址。

保留原完整配置，按实际版本合并以下字段，不能用此片段替换整个 DNS：

```yaml
dns:
  enable: true
  listen: 127.0.0.1:53
  default-nameserver: ['https://223.5.5.5/dns-query#DIRECT']
  nameserver: ['https://1.1.1.1/dns-query#出口选择']
  proxy-server-nameserver: ['https://223.5.5.5/dns-query#DIRECT']
  # 保留全部已核实的保护域名政策，并将它们放在 geosite 之前。
  nameserver-policy:
    '+.anthropic.com': ['https://1.1.1.1/dns-query#出口选择']
    '+.claude.ai': ['https://1.1.1.1/dns-query#出口选择']
    geosite:private: ['rcode://name_error']
    geosite:cn: ['https://223.5.5.5/dns-query#DIRECT']
```

这里的公共解析器和 selector 名称为示例；`default-nameserver` 的字面 IP DoH 防止 bootstrap 悄悄变成明文 53。`proxy-server-nameserver` 仅用于节点域名。国内 DNS 直连是明确政策，不要宣称所有 DNS 都经国外节点。

private 明确拒绝仅适用于没有 LAN 名称解析需求的机器。有 LAN DNS/企业 split DNS 时保留经过核验的本地解析方案；不要把私有名称交给公共解析器，也不要为统一模板破坏原内网解析。若确需物理 LAN DNS，后续 PF 必须在通用 53 阻断之前设置限定接口/目标/协议的例外并测试；仅把目的地址列入 LAN 表不能越过前面的端口阻断。

执行顺序：

1. 确认本地 TCP/UDP 53 可用、服务模式有权限监听。已有 DNS 服务冲突先解决，不抢占监听。
2. 修改真实活动 profile、必要的专属 DNS 整体覆写与导出模板；重新激活订阅，核对生成配置、监听与 selector 未变。
3. 本地 UDP 和 TCP 查询都成功后，再把获授权的当前网络服务 DNS 设为 `127.0.0.1`；回读 `networksetup` 与 `scutil --dns`，检查 scoped resolver 和其他 VPN 的解析配置。
4. 系统 DNS 不支持填写 `127.0.0.1:1053`；只有 1053 监听时不能直接填 127.0.0.1。也不要加第二个公网 DNS 当备用。
5. 重载配置后再次确认本地监听、系统 DNS 和有效解析。未测试的网络服务/新网卡切换要标明；不要无差别修改所有适配器。

macOS TUN 对 LAN DNS 的接管存在平台边界。系统解析入口、TCP/UDP 劫持和物理出站规则需要分别核验。[Mihomo DNS](https://wiki.metacubex.one/config/dns/)、[TUN](https://wiki.metacubex.one/config/inbound/tun/)。

### 系统 DNS 地址不等于最终上游

在 Clash Verge Rev v2.5.2 的 macOS fake-IP/TUN 路径中，`use_tun` 会先恢复系统 DNS，再设置 `114.114.114.114`；退出时也会恢复先前记录。该行为与 GUI 的“DNS 覆写”开关控制的核心配置不是同一层。[固定版本源码](https://github.com/clash-verge-rev/clash-verge-rev/blob/v2.5.2/src-tauri/src/enhance/tun.rs)、[系统 DNS 设置脚本](https://github.com/clash-verge-rev/clash-verge-rev/blob/v2.5.2/scripts/set_dns.sh)。其他版本重新核对，不推广成所有客户端行为。

如果该地址的 UDP/TCP 查询已被 TUN 接管，真正上游仍可能是 `https://1.1.1.1/dns-query#出口选择`。看到公网 DNS 地址不能直接判泄漏；看到 fake-IP 也不能直接判国外 DoH 已走代理。分别测试系统解析、本地监听、针对系统 DNS 的 UDP/TCP 请求、独特上游查询、物理出口捕获和 PF 正反对照。

这种受客户端管理的模式，仅在确认 TUN 接管、物理 DNS 直出阻断且上游策略保持时判通过，并明确系统显示的地址。不把一次 `networksetup` 修改称为持久修复，不篡改应用包内脚本、偷偷改成 redir-host 或增加竞争写 DNS 的循环。若用户明确要求固定 loopback，按当前版本受支持的设置/生命周期接口另行实现并重启验收；无法稳定保留时报告限制。

直接给 Mac 填 `1.1.1.1` 或 `8.8.8.8` 不会自动启用 DoH。增加解析器也不保证更快或更隐私；如确有需要，在核心内验证加密端点、相同 selector 和故障阻断，不能引入直连备用解析。国内加密 DNS DIRECT 保留为用户明确的分流政策。

### 重启验收与 TCP 正常、UDP 丢失

1. 记录用户允许的重启层级：配置重载、核心重启、整个 GUI 正常退出重开、整机重启。保存当前 selector、真实出口、核心 PID、启动时间、系统 DNS、TUN 及 PF；私有备份后才执行。
2. 固定原 selector，不为重启验收切到新节点。提示核心停止会令现有长连接重连，保护规则不关闭。GUI 重开应有新进程/新启动日志；只关窗口或打开首页不算重启。
3. 重开后同时测试 `127.0.0.1:53` 的 UDP 和 TCP，并回读系统 DNS、scoped resolver、实际系统解析。配置含 `listen`、`xray -test` 或只有 TCP LISTEN 都不能证明 UDP DNS 可用。
4. 若 UDP 超时且 socket 缺失而 TCP 正常，检查占用、核心身份和启动日志，记录证据后再处理。参考案例中同地址重载未恢复，重新绑定 DNS 监听后恢复；后续完整应用重启两种监听均正常，最初丢失的根因仍未知。此经验不是要求每次启动改端口，也不证明任何特定版本必然有该缺陷。需要重新绑定时先验证临时端口空闲，保存完整运行配置与 selector，只做一次有界实验后恢复，不写常驻修复循环。
5. 同窗测试物理接口 DNS/STUN 和普通 TCP/UDP 绕行失败、对应 PF 丢弃计数增加；已选节点 HTTPS 与国内业务成功。捕获必须确认已开始并有正常节点包作为正对照，等待缓冲输出后结束；只记录必要头部/计数，snaplen 按链路与协议核算，不保留 payload。
6. 用新的解析查询避免缓存冒充上游通信；核对仍是原 selector，无备用节点接管。国外上游路径、应用长连接和所有 IPv6 场景分别标状态，不用一次 IP 请求替代。
7. 保存重启期间的状态变化、最终结果及临时进程清理证据。整机重启若用户推迟，写明待做；现有开机日志和手工运行 LaunchDaemon 不能替代一次新的整机重启后验收，也不证明开机所有瞬间均受保护。

## 3. Chrome 与 Safari 必须分别处理

### Chrome

核对当前版本和管理策略来源；在真正生效的 macOS 管理策略中合并，而非覆盖整个 plist：

| 策略 | 值 | 含义 |
|---|---|---|
| `WebRtcIPHandling` | `disable_non_proxied_udp` | 限制非代理 UDP；不是关闭 WebRTC API |
| `DnsOverHttpsMode` | `off` | 使用受保护的系统解析路径；Clash 上游仍使用 DoH |

参考管理策略文件为 `/Library/Managed Preferences/com.google.Chrome.plist`，实际安装方式和 MDM 优先级需确认。先完成系统 DNS 保护再停用浏览器自己的 DoH，避免中间阶段退回未保护的系统 DNS。不能与组织管理策略相冲突或绕过 MDM。

分别记录 plist 已配置、浏览器已采纳、行为实测。若工具不能打开浏览器内部政策页，不换接口绕过工具限制；保留采纳状态未知，并使用实际测试补充，不能仅凭文件存在判定已生效。[Chrome WebRTC 策略](https://chromeenterprise.google/policies/#WebRtcIPHandling)、[DNS 策略](https://chromeenterprise.google/policies/#DnsOverHttpsMode)。

### Safari（包括默认浏览器）

系统 DNS/PF 也覆盖相应 Safari 路径，但 Chrome 策略不会应用于 Safari。“防止跨站跟踪”“隐藏 IP 地址”和 WebRTC 是不同机制。检查这些已有设置，不为了统一出口就盲目关闭隐私保护。

2026-10-11 在 Safari 26.5.2 尝试 `WebKitPreferences.peerConnectionEnabled=false` 后，应用重启将其恢复为 true。**这不是有效的通用关闭方法**；不把这个写入命令放进安装步骤。遇到类似设置必须回读并测试，未生效就恢复原有键/不存在状态。WebKit 源码存在某个偏好，不证明 Safari 产品允许用该键持久控制。

不要勾选开发选项“Disable ICE Candidate Restrictions”：它会放宽地址候选限制。也不要为了“禁用 WebRTC”随意改变编解码器、关闭加密或启用全机 Lockdown Mode。[WebKit WebRTC 隐私说明](https://webkit.org/blog/7763/a-closer-look-into-webrtc/)、[开发设置含义](https://webkit.org/web-inspector/device-settings/)。

缺少验证有效的浏览器控制且要求防止绕行时，使用下一节已授权的 OS 方案。WebRTC 仍可能返回 mDNS 候选或通过已选代理工作；目标是限制真实公网绕行，不伪装、篡改或捏造候选地址。Private Relay/隐藏跟踪器 IP 可能另外改变某些请求的出口；普通 IP 检测页通过不能证明所有跟踪器看到同一个 IP，需要单列审计或保留未知。

## 4. 可选 PF 防绕行：按目标主机生成

模板：[macos-leak-guard.pf.in](../assets/macos-leak-guard.pf.in)。替换 `REPLACE_UID` 和 `REPLACE_TUN_INTERFACE`，不要照搬某次案例的用户 ID 或 utun 编号。参考前提为 root 服务模式的 Mihomo 与普通用户浏览器分别拥有 socket，必须检查实际网络进程身份及探针计数；不能仅根据主应用 UID 推断所有 helper。

模板顺序：本地 loopback/TUN 进入代理 → 物理 DNS/STUN 端口阻断 → 当前 UID 的其余公网 TCP/UDP 直出阻断。局域网例外保留，但 DNS/STUN 通用阻断位于其前。它不是包内容识别器，不会识别“Claude 的 DNS”或任意 WebRTC 协议；也不等于所有用户和服务的整机断网锁。

常用 STUN/TURN 的 Mihomo 辅助规则可在用户要求阻断这类端口且接受通话影响时置于业务规则前：

```yaml
- DST-PORT,3478,REJECT
- DST-PORT,5349,REJECT
- DST-PORT,19302,REJECT
```

这三个端口不是完整的 WebRTC 定义。只封它们、只封 UDP 或只开启 TUN 都不能作为任意端口防绕行证据。任意 443 DoH 也不能靠 53/853 端口规则识别；UID 规则约束的是其直接公网连接，核心中的国内 DNS 政策仍须正确。

### 应用与持久化

1. 只读检查 `/etc/pf.conf`、实际主规则、嵌套 anchor、已有精确目标防护、启用状态和状态表。确认新 anchor 可达以及规则次序；前置 `pass quick`/已有状态可能使新规则不被评估。
2. 备份后生成独立 anchor 文件，先运行 `/sbin/pfctl -n -a <实际anchor> -f <生成文件>` 校验。未替换参数、核心身份冲突、anchor 不可达时停止应用。
3. 文件由 root 持有，普通用户不可修改；仅加载该 anchor。不要使用 `pfctl -F all`、全局 `-d`、重载主规则或清空所有连接来安装本功能。原 Claude/其他安全规则保持原语义。
4. 若实际主规则使用 Apple 的 `com.apple/*` hook，可在核验排序后使用其独立子 anchor，并在备份过的持久 pf.conf 加相应 `load anchor`。没有该 hook 时不能假装子 anchor 已运行；按当前规则集设计并校验接入。
5. 开机加载器由 root LaunchDaemon 执行，校验 root 身份、固定文件路径/所有者/权限、有效 hook、语法；只加载本 anchor，验证 DNS 与 UID 阻断标签。持有自己的一份 PF `-E` 引用，令 token 在当前 boot 的 root 私有目录中幂等保存；不能每次加载都累积引用。失败显式退出，不能自动禁用 PF；人工撤销只释放自己的 token，不影响其他组件。
6. 检查加载退出码、live rules/计数和文件持久化。处理开机 hook 未就绪、核心晚于 DNS 启动的顺序；没有实际重启/开机时序测试，必须标记未测，不能保证开机每一瞬间都受保护。

更换网卡、核心运行 UID、TUN 名称或其他 VPN 后重新校验。DNS 指向本地且公网新连接受限时，关闭 Clash 会导致受保护业务失败；不能为恢复联网偷偷加直连例外。用户选择国内 DIRECT 仍由运行中的核心按规则执行，与普通应用绕开核心直出不同。

## 5. 分层验收与停止条件

| 项目 | 最低证据 | 不合格的替代证据 |
|---|---|---|
| 持久性 | 源、profile、脚本、生成配置与再次重载一致；浏览器/服务采用分别记录 | 只写生成文件或只看到 plist |
| 普通出口 | 每个目标浏览器的新 HTTPS 请求返回预期节点出口 | 仅 curl 代理成功、GUI 延迟正常 |
| DNS | 系统解析、本地 UDP/TCP 53、国外 DoH 路径与国内正对照 | fake IP 回答单独证明远端 DNS 出口 |
| WebRTC | 无权限请求的候选收集；区分 mDNS、host、srflx、relay、IPv4/IPv6、API 错误和超时 | 0 候选/构造失败直接判零泄露 |
| 端口阻断 | 物理接口绑定的 TCP/UDP 53、853、常用 STUN，失败且对应 PF 计数增加 | 只有超时，或探针被 TUN 接管 |
| UID 绕行 | 同用户物理绑定 TCP 443、UDP 443/任意非 STUN 端口，失败且 UID 规则计数增加 | 只测试已被端口规则覆盖的 3478 |
| 正常访问 | 同窗已选节点出口成功、国内 DIRECT 成功、原管理路径仍可用 | 全部失败被误当作保护成功 |
| 故障 | 隔离 core 中所选节点失效：国外请求/解析失败、不换节点、国内仍可用 | 关闭生产 TUN 或拿真实公网地址冒充不可达 |

物理绑定方法按当前平台核验。参考 Darwin 头文件中的 `IP_BOUND_IF`/`IPV6_BOUND_IF` 与实际接口索引；仅绑定源 IP、`--noproxy '*'` 或直接访问 IP 不足以排除 TUN。有可用 IPv6 才做其实际出站测试，否则把 IPv6 行为标未测，PF 同时具有 IPv4/IPv6 规则不能替代它。

本地浏览器探针：[webrtc-probe.html](../assets/webrtc-probe.html)。只把 assets 或它的私有副本作为 loopback HTTP 服务根目录；绝不能把凭据/备份父目录公开。使用实际 Safari/Chrome，点击开始，不请求摄像头/麦克风，不发起登录/Chat。候选地址仅在内存分类，页面输出数量/状态；不会上传测试结果。它会向列出的 STUN 服务发网络请求，匿名本地候选也应单独记录。观察期未完成 ICE gathering 要标 `inconclusive`，API 不可用要标 `api-unavailable`，结合防火墙证据解释。

PF 是有状态的。新规则不会自动清除已有连接；保持生产连接时交付“新连接已限制”，不能称为全部旧连接已迁移。确需立即覆盖已有浏览器会话，保存页面工作并按授权范围正常重开浏览器、再测新连接；不要删除全局 states。外部浏览器、Electron、手机 v2box 分别验收。

完成上述适用检查后停止扩展测试，保存时间窗、计数前后、结果/未测项与私有撤销清单。停止自己创建的本地 HTTP 服务、隔离 core 和捕获，关闭临时测试页。提交到技能仓库的只能是通用模板和脱敏经验；不得上传个人策略快照、真实节点地址、密钥或原始捕获。

## 6. 经验归纳（不是新的机器通过记录）

| 参考案例观察 | 以后如何执行 |
|---|---|
| 系统仍指向公网 DNS，Clash 仅监听 1053 | 先验证本地 53，再调整系统 DNS，不以 TUN 已开代替解析验收 |
| Chrome 构造 API 失败在修改前也出现 | 记录基线，不把既有扩展/环境影响归因于新策略 |
| Safari 隐藏开关重启后被恢复 | 判无效、撤回；采用可验证的分层约束 |
| Safari 仍有 mDNS 候选，无公网候选 | 区分匿名本地候选与公网泄露；保留收集超时状态 |
| 常规 STUN 被拦后，任意端口仍需测试 | 用 UID 级规则的独立探针和计数验证绕行阻断 |
| 国内 DIRECT 与国外固定节点同时正常 | 防绕行限制应用入口，核心负责分流；不要把国内全部强制代理 |
| GUI 重开后系统 DNS 又变为公网地址 | 核对版本启动覆写与 TUN 实际接管、物理 DNS 阻断；不以地址字符串单独判泄漏或已修复 |
| 本机 TCP53 可用、UDP53 无监听 | 两种协议独立验收；恢复监听不等于根因已确认；应用重启后再次验证 |
| 新节点 IP 查询成功但 GPT 仍持续重连 | 出口验证与长连接稳定性分开；保留原默认节点，禁止自动切换掩盖失败 |

最终报告分别列 `configured`、`active`、`passed`、`inconclusive`、`not_tested`。端口与 UID 防火墙、浏览器策略、实际网络路径的证据不得互相冒充。不能承诺永不泄露、永不换 IP、匿名或账号免风控。
