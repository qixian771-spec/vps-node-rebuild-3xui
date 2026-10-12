# 操作契约与命令目录

本页的辅助工具全部离线；不自动安装依赖、不修改生产配置。外部目标命令由执行 AI 逐条运行、立即读取退出码；失败停止依赖步骤。工作目录没有特别说明时为本次私有任务目录。

## O0 路径与占位符

从实际打开的 `SKILL.md` 绝对路径确定技能根目录，设 `SKILL_ROOT`；不要假定当前 cwd 或仓库名就是安装路径。`TASK_DIR` 必须为用户允许的私有工作根下新建的目录，用 shell `pwd -P` 得到无符号链接的绝对路径。

下面的大写变量是 shell 变量，**不是工具默认值**。在本次任务卡写明每个值来自哪条检测；命令中的 `<...>` 是必须人工替换的示意，不原样执行。所有含路径变量均加双引号，不把密码/UUID/私钥填入 shell 变量或参数。

```sh
# 将两个示意绝对路径换为已核对的位置；父目录须已存在。
SKILL_ROOT='/absolute/installed/vps-node-rebuild-3xui'
TASK_PARENT='/absolute/authorized/private-work'
TASK_DIR=$(mktemp -d "$TASK_PARENT/node-task.XXXXXXXX")
chmod 700 "$TASK_DIR"
cd "$TASK_DIR"
```

`mktemp`/`chmod`/`cd` 任一个非零即停，不继续下面一条。不在只读且禁止创建文件的任务中建目录；在会话内记录脱敏证据即可。macOS `/tmp` 常为链接，脚本拒绝路径中符号链接：用实际目录的 `pwd -P` 路径；这不是切换数据来源，必须仍指向已确认对象。

## O1 随包 CLI、依赖和统一退出码

技能代码支持 macOS/Linux，Python ≥3.10，仅标准库。`python3 --version` 退出 0 且版本达标后才执行；没有 Python 就停止，不自动找别的解释器或下载。Node ≥18 **只用于 JS 合成测试**，不是日常 CLI 依赖。目标软件依赖在安装手册独立列出。

```sh
python3 "$SKILL_ROOT/scripts/skillctl.py" --help
python3 "$SKILL_ROOT/scripts/skillctl.py" validate --root "$SKILL_ROOT"
python3 "$SKILL_ROOT/scripts/skillctl.py" preflight --platform darwin --require curl --require networksetup
```

Linux 把 `--platform` 明确设为 `linux`，按路线重复 `--require ssh` / `--require openssl` / `--require ss` 等命令名，重复 `--input "$VERIFIED_FILE"` 校验已确认的文件路径。不执行被检查的命令，不证明其版本/权限或授权。只读错误不能当成“未安装”。

| 退出码 | 意义 | 下一步 |
|---|---|---|
| 0 | 本命令声明的有限范围成功；JSON `scope` 指明边界 | 满足任务卡条件才继续 |
| 2 | 参数、编码、JSON、数据库或模板输入无效（argparse 用 stderr，其他用 JSON） | 停止；核对输入来源，不能猜值 |
| 3 | 依赖/路径/平台缺失、文件系统错误或目标已存在 | 停止；不安装依赖、不覆盖、不换来源 |
| 4 | 有效执行但证据不满足：无启动证据、代理未确认、快照超时/完整性不满足 | 标未确认/失败；不判通过 |
| 5 | 权限拒绝，可能有部分产物 | 记录残留，不自动 sudo 或 chmod 源 |
| 6 | 未预期内部错误 | 停止并报告工具错误，不自动换实现 |

工具错误只输出原因代号，不回显原始日志/凭据/完整私人路径；错误不自动重试。任何非零后，检查**本次已知目的目录**是否部分创建，记录后保留；不自动清空目的目录重跑。参数解析帮助退出 0 不算业务验收。

### 一致数据库快照

仅限已授权读取数据库及保存私有备份；在数据库所在 Linux 主机执行（该主机有受核验的完整技能副本和 Python）。`DB_SOURCE` 从 O2 服务/面板证实路径取得；`BACKUP_DIR` 为既有私有父目录下**尚不存在**的子目录。

```sh
python3 "$SKILL_ROOT/scripts/skillctl.py" snapshot --source "$DB_SOURCE" --output-dir "$BACKUP_DIR"
```

退出 0 输出快照 SHA256、五个已知表的存在/列数和 `has_flow_override`，目标文件名固定 `snapshot.sqlite3`，目录 0700/文件 0600。源只读，SQLite backup API 保持一致；未找到源不会创建空源。损坏库为 2，已存在目的为 3，权限为 5；backup 阶段 20 秒期限为 4（初始 quick_check 不在此期限内，大库需单独评估维护窗口）。失败后不自动删部分快照。备份通过不意味着 schema 可写或服务可用。

### PF 仅生成

`TARGET_UID` 来自拟保护网络进程，`CORE_UID` 来自独立 root 核心进程（必须为 0），`TUN_IF` 来自当前实际 utun，`PF_OUTPUT` 是私有目录下尚不存在的文件。

```sh
python3 "$SKILL_ROOT/scripts/skillctl.py" render-pf --uid "$TARGET_UID" --core-uid "$CORE_UID" --tun "$TUN_IF" --output "$PF_OUTPUT"
```

退出 0 是 `configured/file_only_not_loaded_or_persistent`。非法 UID、非 utun 名、身份冲突为 2；已有文件 3。不读取/写入 `/etc`，不执行 pfctl。参数里的 UID/TUN 是调用者证据，不由脚本验证主机实况。

## O2 Linux 只读发现（远端 cwd 为已授权工作目录）

以已有、已校验 host key 的 SSH alias 进入目标，真实端口来自用户/既有 SSH 配置；禁止默认 22。`ssh -G "$SSH_ALIAS"` 只在私有终端筛选 hostname/port/user，不能上传完整 SSH 配置。

在目标端逐条执行：

```sh
cat /etc/os-release
id -u
uname -r
systemctl list-unit-files --type=service --no-pager
ss -ltnp
```

均要求 0；无 systemd/无 ss 就停止这套发现流程，报告当前平台未适配，不按别的发行版命令盲装。只读选择确实管理目标监听的单位，再运行：

```sh
systemctl show "$SERVICE_UNIT" --property=FragmentPath,MainPID,ActiveState,SubState
systemctl cat "$SERVICE_UNIT"
```

单位名从第一组真实结果选择，不默认 `x-ui`。`systemctl cat` 可能含敏感环境，输出留在受控私有上下文，只报告管理器/路径是否确认，不上传原文。MainPID=0 或 ActiveState 非 active 是状态证据，不是假装运行。生成配置/数据库路径从真实启动参数、面板配置和对应版本源码交叉确认；无法定位时停止相关写入。

目标二进制 `--help`/版本输出支持什么才用什么；Xray 常见验证入口为 `run -test -config`，旧别名不是跨版本契约。必须核对当前 `help run` 后将确切 argv 写入卡。

## O3 客户端与 GUI 发现

工具顺序：用户指定 GUI → GUI 的配置/订阅页显示活动项 → 该应用已知配置目录/进程实际启动参数 → 本项 profile、扩展脚本与生成路径 → 本 core API。不要递归扫描用户主目录找凭据。

GUI 工具调用不规定不存在的统一 API：使用执行环境已提供的浏览器/桌面工具，先读取其文档；记录页面标题、字段、当前值、操作后状态。实际工具不支持的动作停止，不改用隐藏接口绕过工具限制。

本 core API 在**已证实** loopback/UDS 控制器上只调用：`GET /version`、`GET /configs`、`GET /proxies`、`GET /rules`。使用当前版本 API 文档确认字段；200 且结构合法才能取值，401/403/404/超时停止，不猜另一端口/路径。secret 仅从受限文件读入 HTTP 客户端内存，不放 curl 参数或打印响应全集。只提取 selector 当前值、组类型、版本、TUN 状态及本次规则证据。此包不提供通用 API 客户端，因此实际 HTTP/UDS 工具及参数必须落入适配卡，不能引用不存在的 `skillctl api`。

仅靠源配置不能确定当前 selector；不得修改缓存来“读取”状态。

## O4 macOS 只读状态

在 Mac 逐条执行，全部必须记录退出码：

```sh
sw_vers
id -u
networksetup -listallnetworkservices
scutil --dns
ifconfig -l
```

`NETWORK_SERVICE` 从 listallnetworkservices 中匹配正在使用的接口（不能盲设 Wi-Fi），然后：

```sh
networksetup -getdnsservers "$NETWORK_SERVICE"
networksetup -getwebproxy "$NETWORK_SERVICE"
networksetup -getsecurewebproxy "$NETWORK_SERVICE"
```

0 可能表示 DHCP DNS 没有显式条目，不是错误；完整输出保存在私有记录。权限拒绝/非零停止相应检查。通过已核对 PID 的 `ps -p "$CORE_PID" -o pid=,uid=,comm=` 确認核心身份；PID 从运行 GUI/core 证据取得，不用模糊进程名 kill。CLI 以 `command -v claude` 判断 PATH 独立版本，退出 1 是缺失，不能初始化配置假装已经采用。

PF 只读若已授权且已有 sudo 能力：`sudo -n /sbin/pfctl -s info`、`sudo -n /sbin/pfctl -sr`；非零停止该检测，不开启 PF 来取得输出。读取 anchor 必须先从主规则找到真实名称。

## O5 新连接出口与 DNS 检查（会联网）

前提：显式网络探针授权、已验证的本地 mixed/HTTP 端口、预期出口来自当前有效记录而非名称；这些公共服务为显式选择的检查端点，失败不换来源。

```sh
curl --fail --silent --show-error --connect-timeout 5 --max-time 20 --noproxy '' --proxy "http://127.0.0.1:$MIXED_PORT" https://api.ipify.org
curl --fail --silent --show-error --connect-timeout 5 --max-time 20 --noproxy '' --proxy "http://127.0.0.1:$MIXED_PORT" https://checkip.amazonaws.com
```

两条独立新 curl 进程逐条执行。退出 0 且响应可解析为 IP、等于本次预期才通过；5/6 解析失败，7 连接失败，22 HTTP失败，28 超时，35/60 TLS失败，其余非零原样记录停止。第一条失败不把第二条当替代成功来源；只有继续取证的任务卡明确授权时才继续独立对照。不能加 `-k`。

TUN 验收使用同一 URL 和超时但 `--noproxy '*'` 且不加 `--proxy`；它只是不使用应用代理，**不是裸直连**。需核心连接/路由证据。国内正对照 URL 由用户业务或已确认无账号公共页面选定，必须回读匹配 DIRECT 规则；HTTP 200 本身不证明 DIRECT。

DNS：`DNS_PORT`、系统 DNS 取自运行状态；`PROBE_NAME` 使用用户许可的公开测试域名下新 nonce（没有许可域名时用固定公共域名但缓存影响标 inconclusive）。

```sh
dig @127.0.0.1 -p "$DNS_PORT" "$PROBE_NAME" A +tries=1 +time=3
dig @127.0.0.1 -p "$DNS_PORT" "$PROBE_NAME" A +tcp +tries=1 +time=3
```

dig 0 只说明收到应答，必须检查 RCODE/ANSWER/SOA；受控不存在 nonce 的 NXDOMAIN 可作为已获得应答证据，SERVFAIL 不能通过；9 无响应、1 参数错误、其余非零停止。DoH上游出口仍需专题定义的同窗证据，fake IP 不算。没有 dig 则按 O1 停止，不临时换成测试口径不同的系统 resolver。

## O6 隔离配置语法校验

前提：`CORE_BIN` 是 O3 确认的实际 Mihomo 可执行文件、已核对 `-h` 支持 `-t/-d/-f`；`CHECK_DIR` 独立新目录；`CANDIDATE` 私有副本；所需 geodata 已在该目录且来源/哈希明确。缺离线数据停止，不能让语法检查偷偷下载数据。禁止联网时只使用不引用外部数据/URL 的合成配置；真实配置缺数据就标未执行。

```sh
"$CORE_BIN" -t -d "$CHECK_DIR" -f "$CANDIDATE"
```

0 且明确配置测试成功仅代表该版本语法通过。非零为失败；输出可能含节点字段，只保存私有原文、交付脱敏结论。不启 TUN、不更改 OS 代理、不使用生产 cache 目录。

## O7 隔离故障实验与进程生命周期

本包没有核心进程编排脚本。执行 AI 必须在本次卡内准备可审阅的隔离启动脚本：精确二进制、独立数据/日志目录、本地监听端口、TUN=false、OS代理不变、默认 selector、到期时限、记录子 PID、try/finally 关闭并 wait 的完整代码。**没有完成这些前提就不得启动临时 core。** 禁止直接套用生产完整配置引入 TUN、redir/tproxy、自动下载或相同控制器。

故障注入只改测试副本中已选节点，使用刚验证未监听的 loopback 端口，保留其余节点；不假定端口 1 永远关闭。使用原语法校验、正对照和同样 O5 探针后，所选路径失败且 selector 不变才支持 fail-closed；国内 DIRECT 正对照必须成功。核心不支持 UDP 则禁止使用其他节点替其处理 UDP。

停止规则：启动错误、正对照失败、测试期限到达、用户暂停，均结束实验，finally 只停止自己的 PID。清理失败也记失败；不要删除日志和产物来隐藏问题。隔离测试不能证明生产 GUI/TUN 已生效。

## O8 Claude 本次启动证据

从应用实际本次启动/用户记录取得带时区 `SINCE`，单个 `CLAUDE_LOG` 从该版本的日志位置证实（不是把两个猜测路径都扫一遍）。`LOG_TZ` 为日志无时区时间戳的已证实偏移，如 `+08:00` 或 `-07:00`，不猜时区。

```sh
python3 "$SKILL_ROOT/scripts/skillctl.py" logcheck --source "$CLAUDE_LOG" --since "$SINCE" --log-timezone="$LOG_TZ" --port "$MIXED_PORT"
```

只读最多末尾 1 MiB，只输出时间与布尔值。0 仅确认限定窗口最后一条代理事件为该版本已识别的 fixed-loopback 文案且无 PAC 事件；4 是未确认，不是未安装或成功。不存在路径为 3，损坏编码/代理事件时间不可解析为 2。新版本日志文案不同先停止、查源码契约，不放宽匹配条件冒充通过。不据启动日志保证业务或DNS路径。

## O9 WebRTC 与 PF 验收的边界

PF 文件语法（仅在 macOS、权限已确认、文件已生成）：

```sh
/sbin/pfctl -n -a "$VERIFIED_ANCHOR" -f "$PF_OUTPUT"
```

0 是语法；非零停止，不加载。hook/规则次序/旧 states/主机权限由专题确认，语法成功不能代表 active。没有获验证的安装器和开机验收，明确交付“仅模板，未部署”。禁止 `pfctl -F all`、全局 `-d`、重载主规则取得测试通过。

浏览器探针：整个 `assets/` 作为唯一 loopback HTTP 根，端口是已确认空闲的本机高位端口。

```sh
python3 -m http.server "$PROBE_PORT" --bind 127.0.0.1 --directory "$SKILL_ROOT/assets"
```

前台独占终端任务，记录该进程 PID，看到 Serving 且 loopback GET `/webrtc-probe.html` 200 后用授权浏览器打开相同 URL；不得暴露备份父目录。点击“开始检查”会联网访问页面列明的两个 STUN 服务，不能在禁止联网任务中点击。每项 7 秒观察期，输出数量/完成/错误；没有候选不能判零泄漏。完成后在该终端 Ctrl-C，确认该 PID 退出、端口不再监听；不要结束其他 Python 进程。无浏览器授权时用合成测试，不称为真实 WebRTC 验收。

## 版本/主机适配卡：没有通用参数的操作

用于面板安装/API/GUI、核心生命周期、PF持久化等依赖实际环境的动作。它不是把空白留给“自行配置”：**先完成此卡、验证命令存在，再允许执行**。无法完成时交付阻塞和已完成证据。

| 必填字段 | 可接受内容 |
|---|---|
| 目标/版本/工作目录 | 本次真实检测，私有绝对路径；服务端或客户端不能混用 |
| 依据 | 该精确版本 help、官方源码/文档的 commit/tag及相关字段；禁网时只用已有核验材料，否则阻塞 |
| 读取操作 | 精确工具名/参数或GUI页面字段；只读成功状态/非零退出码含义 |
| 写入操作 | 完整 argv 或 API 方法/路径/字段/schema；安全凭据输入；GUI逐个字段和保存动作 |
| 前提与范围 | 备份位置、当前状态、已有授权、不可变项、接口/UID等适用性 |
| 通过与停止 | 预期输出/HTTP码/回读字段；未知响应或非零停止，不自动换接口 |
| 测试与证据 | 隔离/真实分别列；观测窗口、正对照、成功标准、未测边界 |
| 结束处理 | 预定临时进程清理；生产失败保留现状，不自动回滚；恢复须独立卡 |

每条卡里的命令先以 `--help`/源码确认参数（不能为了看帮助运行不支持帮助的安装脚本）。工具没有暴露版本/参数时，报告未适配，而不是宣称所有 fork 可用。
