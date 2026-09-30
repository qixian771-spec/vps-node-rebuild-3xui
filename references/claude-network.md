# Claude 桌面端与 CLI：固定代理和 DNS 路由

当用户要求 Claude 桌面端、Claude Code 随 Clash 的手动节点选择使用同一出口，并避免这些请求走本地公网出口时，读取本文件。三节点分组、国内直连、DNS 源与策略顺序先按 [clash-routing-dns.md](clash-routing-dns.md) 处理。本文件只补充 Claude 的应用设置与验收。

保护范围是请求的网络路径与域名解析路径；不能据此承诺匿名、账号安全、业务地区可用或永不封号。这里的“本地 IP”指本机原有公网出口，不包括必要的本地代理地址。配置文件已保存、应用启动采用配置、请求通过代理，是三个不同的验收状态。

下文的“本轮”与版本实测均指 **2026-09-30 的参考案例**，不是下一次任务的运行证据；每次应用都要重新确认，不能直接填入本次 `active/pass`。

## 1. 先确定作用范围

- 只检查版本、可执行文件位置、代理变量、endpoint 字段和相关启动日志。不要读取或输出登录凭据、API key、会话历史；不要把个人配置或日志放进公开仓库。
- 独立 CLI、桌面 Chat、桌面 Code/Cowork、SSH/云端会话的执行位置不同。本机代理设置不能证明远端或云端也使用相同出口。
- 从当前有效配置中只提取实际 provider、网关、MCP、OTLP 等端点的 hostname，形成私有的目的地主机清单；剔除 URL 用户信息、路径、查询参数和凭据。若不是 Anthropic 直连服务，后文六个后缀不能代替这个清单：实际目标也要逐项核对规则、DNS、连接链和代理覆盖。保留既有 provider，不为了满足核心域名测试而切换服务。
- 启停应用、改变系统代理、切 TUN 或故障测试应在当前任务授权范围内进行。不要为验证自动关闭生产防护、清理用户连接、发送聊天消息或退出账号。
- 对本次未运行的路径标记 `configured` 或 `not-tested`。例如 CLI 未安装，即使已准备用户设置，也不能记为 `pass`；SDK 内嵌二进制不是用户 PATH 中的独立 CLI。

## 2. Claude 域名必须同时固定连接和解析路径

按执行当天的官方清单复核。2026-09-30 核验的桌面核心后缀如下；用后缀规则覆盖根域及动态子域，不硬编码解析后的 IP。

| 核心后缀 | 规则和 DNS 政策 |
|---|---|
| `anthropic.com` | `DOMAIN-SUFFIX` → 同一手动 selector；`+.anthropic.com` → 经该 selector 的 DoH |
| `claude.ai` | 同上 |
| `claude.com` | 同上；包括 `platform.claude.com`、`code.claude.com` |
| `claude.app` | 同上 |
| `claudeusercontent.com` | 同上；包括 bridge 与动态内容子域 |
| `claudemcpcontent.com` | 同上 |

来源：[桌面网络访问要求](https://code.claude.com/docs/en/desktop#network-access-requirements)。这些是网络保护政策，并非每个根域都提供可测试的 HTTPS 页面。本轮 `claude.app`、`claudemcpcontent.com` 验收了规则和 DNS 政策，未逐个子域测试 TLS 应答。

当前独立 CLI 官方另列两项**可选遥测**：`http-intake.logs.us5.datadoghq.com`、`browser-intake-us5-datadoghq.com`。若保留遥测，将这两个精确域名也固定到同一出口及 DoH；不要扩大成所有 Datadog 客户域名。来源：[CLI 网络要求](https://code.claude.com/docs/en/network-config#network-access-requirements)。

`sentry.io`、`sentry-cdn.com`、`statsig.com`、`statsigapi.net`、`statsigcdn.com`，以及实际版本涉及的 Statsig CDN 域名，只能作为兼容项。部署时重新核对官方资料或本机静态应用代码中的网络目的地；不要把旧列表、猜测或动态 CDN 域名写成永远必需的核心清单。核对兼容项不需要读取用户访问历史。

这些明确域名的连接规则必须位于国内 `GEOSITE/CN`、`GEOIP/CN` 等直连规则之前；DNS 的明确域名政策也先于地理分类政策。路由和 DNS 使用同一个名称，不能一个指向手动组、另一个指向独立自动组。增量示例：

```yaml
# 合并进原有配置；不要用这个片段替换完整规则或完整 DNS。
rules:
  - DOMAIN-SUFFIX,anthropic.com,出口选择
  - DOMAIN-SUFFIX,claude.ai,出口选择
  - DOMAIN-SUFFIX,claude.com,出口选择
  - DOMAIN-SUFFIX,claude.app,出口选择
  - DOMAIN-SUFFIX,claudeusercontent.com,出口选择
  - DOMAIN-SUFFIX,claudemcpcontent.com,出口选择
  - DOMAIN,http-intake.logs.us5.datadoghq.com,出口选择
  - DOMAIN,browser-intake-us5-datadoghq.com,出口选择
dns:
  nameserver-policy:
    '+.anthropic.com': ['https://1.1.1.1/dns-query#出口选择']
    '+.claude.ai': ['https://1.1.1.1/dns-query#出口选择']
    '+.claude.com': ['https://1.1.1.1/dns-query#出口选择']
    '+.claude.app': ['https://1.1.1.1/dns-query#出口选择']
    '+.claudeusercontent.com': ['https://1.1.1.1/dns-query#出口选择']
    '+.claudemcpcontent.com': ['https://1.1.1.1/dns-query#出口选择']
    'http-intake.logs.us5.datadoghq.com': ['https://1.1.1.1/dns-query#出口选择']
    'browser-intake-us5-datadoghq.com': ['https://1.1.1.1/dns-query#出口选择']
```

DoH 地址和 selector 名称是示例，使用用户实际选择并验证可用的配置。DNS 引导、节点域名解析、国内解析、Clash Verge 的持久源/merge/script 优先级都按 [clash-routing-dns.md](clash-routing-dns.md) 核对；不能只改生成的运行文件。不要新增 DNS fallback 或失败后直连策略。

## 3. 独立 Claude Code 使用用户级代理环境

在实际用户配置目录的 `settings.json` 中**合并**下面的 `env`；通常为 `~/.claude/settings.json`，如果设置了 `CLAUDE_CONFIG_DIR`，先确认真实位置。保留其他设置，避免项目配置或 managed policy 覆盖后仍误报成功。[设置作用域与优先级](https://code.claude.com/docs/en/settings)

```json
{
  "env": {
    "HTTP_PROXY": "http://127.0.0.1:7890",
    "HTTPS_PROXY": "http://127.0.0.1:7890",
    "http_proxy": "http://127.0.0.1:7890",
    "https_proxy": "http://127.0.0.1:7890",
    "NO_PROXY": "",
    "no_proxy": ""
  }
}
```

`7890` 必须替换为已验证的本地 HTTP/mixed 监听端口。大小写都设成同值，避免遗留小写变量抢先；空 bypass 值避免公网域名绕过。不要设成 SOCKS，不修改 `ANTHROPIC_BASE_URL` 或 TLS 校验来解决代理问题。设置比仅在 shell 中 export 更适合后台代理进程；版本和 Desktop 托管会话的读取范围按[当前 network-config](https://code.claude.com/docs/en/network-config)核验，旧 corporate-proxy 文档不能作为依据。

HTTPS 经 HTTP 代理时，应以目标主机名建立 CONNECT，由代理侧解析目标；同时确认 Mihomo 的解析使用上节固定 DoH。TUN 关闭而本地 HTTP 代理仍在时，这类请求仍可通过代理；代理不可用应报错。不能据此证明所有子进程都遵守代理变量，也不能替代实际 CLI 验收。

## 4. macOS 桌面端使用原生固定代理键

优先核验 `egressProxyUrl`，不要凭 Electron 通用参数推断所有应用网络均受控。原生键的官方文档标注自 1.44121.1 起支持；本轮 macOS Claude **2.16120.0** 的静态 schema 同时允许 `1p/3p`，并在普通桌面启动时实际出现固定代理确认日志。不同版本/平台必须重新查官方说明及本机采用证据，不能照搬版本结论。

macOS 用户配置位置为 `~/Library/Application Support/Claude-3p/configLibrary/`。这是本轮普通桌面实际读取的位置，**不是**普通 `Claude/claude_desktop_config.json` 中随意增加的嵌套代理对象。[官方配置位置与 schema](https://claude.com/docs/third-party/claude-desktop/configuration)

目录完全不存在、且没有 managed 配置覆盖时，可用以下无凭据模板初始化。示例 UUID 仅代表本地配置 ID；为新的配置生成新 UUID，两个文件保持一致。

`configLibrary/11111111-2222-4333-8444-555555555555.json`：

```json
{"egressProxyUrl": "http://127.0.0.1:7890"}
```

`configLibrary/_meta.json`：

```json
{
  "appliedId": "11111111-2222-4333-8444-555555555555",
  "entries": [
    {"id": "11111111-2222-4333-8444-555555555555", "name": "固定代理"}
  ]
}
```

已有 `configLibrary` 时，先定位 `appliedId` 对应的活动文件，只修改代理字段；保留 entries、provider、账号模式及其他原字段。固定出口变更还要移除本地活动配置中的 `egressProxyPacUrl`：两键同时存在时 PAC 优先，单加 `egressProxyUrl` 并不能固定出口。先备份再做这项有范围的代理修改，不删除其他配置。不要用上述纯代理模板覆盖已有目录、重写 meta、切换活动 provider。若存在 MDM 配置，先按官方优先级判断它是否接管代理；不要靠写用户文件绕过 managed policy。MDM 中仍有有效 PAC 时，需要在获授权的实际策略源处理，否则标记固定代理未生效。只设置代理键不需要增加 `inferenceProvider` 或 `deploymentMode`。

固定代理不可达时请求失败；**禁止以 `egressProxyPacUrl` 作替代或兜底**，因为 PAC 下载失败可能直连。原生键保留 loopback/`.local` bypass 供本地服务使用，这不包含 Anthropic 公网域名。改变配置后要在已授权的完整应用启动时验证，不能把“保存成功”当作“已采用”。[官方桌面网络代理行为](https://claude.com/docs/third-party/claude-desktop/network-proxy)

原生更新器按 OS 代理处理；外部浏览器按浏览器/系统网络设置处理。相应范围需要另验系统 HTTP(S) 代理与 TUN。helper scripts 和忽略代理环境的程序也不能据此保证阻断。应用代理、系统代理、TUN 都是各自范围内的路由措施，未部署并验收网络层阻断时，不承诺 Mihomo/TUN 被关闭后整个应用仍无法直连。不要为修复启动失败而自动禁用这些防护。

## 5. 不发送 Chat 的验收

| 层次 | 可以记为通过的证据 | 不能推出的结论 |
|---|---|---|
| 持久配置 | 活动 profile/meta 一致，CLI env 同值，实际运行规则和 DNS 政策一致 | 应用已采用、业务已可用 |
| 桌面启动 | 本次启动的 `egress-proxy` 固定地址确认；普通模式运行目录证据 | Chat 推理已通过 |
| 网络路径 | 指定探针的 TLS 证书校验通过，连接链含 selector/所选节点，DNS 链符合政策 | 账号安全、所有 endpoint 都可用 |
| 故障阻断 | 在隔离配置/进程中使所选路径失效后请求失败，其他节点不接管 | 生产 TUN 关闭后整个 OS 有 kill switch |

只检查本次启动时间之后的代理行，不导出整份日志。下面片段是只读筛选器；把参数改为本次启动的**本地时间**，在用户自行启动或当前任务已授权启动之后执行，不会启动应用。

```sh
python3 - '2026-09-30 08:13:00' <<'PY'
from pathlib import Path
from datetime import datetime
import json, re, sys
since = datetime.strptime(sys.argv[1], '%Y-%m-%d %H:%M:%S')
paths = [Path.home() / 'Library/Logs/Claude/main.log',
         Path.home() / 'Library/Application Support/Claude/logs/main.log']
found = []
for path in paths:
    if not path.is_file():
        continue
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 1024 * 1024))
        lines = stream.read().decode('utf-8', 'replace').splitlines()
    for line in lines:
        if '[egress-proxy]' not in line:
            continue
        stamp = re.search(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}', line)
        if not stamp:
            continue
        time = datetime.strptime(stamp.group().replace('T', ' '),
                                 '%Y-%m-%d %H:%M:%S')
        if time < since:
            continue
        found.append({'time': stamp.group(),
                      'fixed_local_proxy':
                      'pinned to fixed proxy at 127.0.0.1:7890' in line,
                      'os_proxy_ignored': 'OS proxy settings ignored' in line,
                      'pac_detected': 'PAC script' in line})
print(json.dumps({'proxy_startup_checks': found}, ensure_ascii=False))
PY
```

筛选器只输出布尔值与时间。实际端口不为 `7890` 时同步改匹配值；无匹配应记 `not-confirmed`，不能猜测已采用。如检查 native helper 的 stdout，也只提取代理/启动状态，不打印账号、完整 URL、token 或聊天内容。

对无凭据的公开 HTTPS 探针，HTTP `403` 与成功校验的 TLS 只能证明传输已抵达返回该响应的服务，**不代表 Claude 业务、登录或推理可用**。不要降低 TLS 校验，也不要自动拿真实 API key 或发送聊天来补齐验收。只统计本次明确探针的连接链与规则；没有业务操作授权时，把业务项保留为 `not-tested`。

## 官方核验入口

- [Claude Code network-config](https://code.claude.com/docs/en/network-config)：代理变量、版本/作用域差异、CLI 网络要求。
- [Claude Code settings](https://code.claude.com/docs/en/settings)：用户位置和覆盖优先级。
- [Desktop 网络要求](https://code.claude.com/docs/en/desktop#network-access-requirements)：核心域名及动态 CDN。
- [Desktop 原生 network-proxy](https://claude.com/docs/third-party/claude-desktop/network-proxy)：固定代理、PAC 行为及例外。
- [Desktop configuration](https://claude.com/docs/third-party/claude-desktop/configuration)：配置位置、键及 managed 优先级。
- [Mihomo DNS](https://wiki.metacubex.one/config/dns/)：`nameserver-policy` 与 `#代理组` 指定解析路径。
