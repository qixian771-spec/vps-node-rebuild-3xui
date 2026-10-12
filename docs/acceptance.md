# 独立交付验收记录

日期：2026-10-12。审查基线：`910bb45`。范围与任务卡见 [改造方案](delivery-plan.md)。本次执行仅修改仓库及隔离测试产物，没有变更用户当前 Clash、默认节点、系统 DNS/PF、浏览器、Claude 或 VPS。

## 里程碑与整体

| 里程碑/任务卡 | 实际证据 | 验收 | 提交方式 |
|---|---|---|---|
| M1 审查/方案 | 基线12文件逐一读取；A1–A11逐项列出代码/说明证据；没有假定已有脚本 | passed | 审查与任务卡随本次实现提交 |
| M2/C1 编排 | 入口从133行缩为40行；runbook G0–G5、R0–R6；operations O0–O9；server S0–S6；安装和完整任务卡 | walkthrough通过，范围见下表 | 实现提交中的文档 |
| M2/C2 工具 | 六个真实CLI子命令；明确0/2/3/4/5/6退出码；WebRTC超时生命周期修复 | code_test通过 | 实现提交中的scripts/assets |
| M3/C3 测试与包 | Python19项、JS7项；22文件manifest及引用闭包；源码及安装后验证 | passed，非生产验收 | tests/与CI工作流 |
| M4/C4 交付 | diff检查、语义/范围复核、隐私检查、官方依据复核、已授权GitHub推送 | 本地通过；实现提交远端SHA一致，四组CI全部success（见下方固定链接） | 实现提交与后续CI证据提交 |
| 整体 | 七路线均有进入/前提/动作/通过/停止/测试/交付；已测与未执行分开 | 本次“技能交付”范围通过；不宣称生产部署通过 | Git历史和精确SHA的Actions记录 |

## 发现问题与处理

| 审查项 | 结果 |
|---|---|
| A1/A9 编排不足 | 短入口、七路线、逐步门槛、精确适配卡；只读任务检查后结束 |
| A2 安装不完整 | 显式manifest复制；不覆盖已有安装；断链/缺资源非零；安装后工具和测试可运行 |
| A3 数据库风险 | 提取只读一致快照；撤掉硬编码SQL写入示例，未知模型停止，不补列 |
| A4 全局sysctl副作用 | 改为独占创建目标文件，仅sysctl -p应用该文件；生产未执行 |
| A5 请求管道掩盖错误 | 删除猜JS/API管道；受支持接口必须有版本适配卡 |
| A6 日志无证据仍成功 | 单路径、时区/端口参数、有限读取；无证据/后续未确认/PAC返回4 |
| A7 PF实现与描述不一致 | 可生成模板；不存在的自动加载/开机功能明确排除，不能据模板宣称已部署 |
| A8 WebRTC超时后继续协商 | 超时/关闭状态阻止迟到offer调用setLocalDescription；晚到reject不产生未处理拒绝 |
| A10 无测试/CI | 合成行为测试、包完整性、安装后测试；Linux/macOS、Python3.10/3.13 CI |
| A11 住宅代理误判 | 代理账户≠SSH管理；不直接改VLESS/XUDP、不自动加前置中转 |

## 代码测试：实际运行

本机：macOS，Python3.13.7、Node24.15.0。不是目标软件最低兼容版本的替代证据；最低版本在CI矩阵另验。

| 命令/检查 | 实际结果与范围 |
|---|---|
| `python3 scripts/skillctl.py validate` | 退出0；22个包文件、全部本地Markdown引用存在；检查结构而非生产语义 |
| `python3 -m unittest discover -s tests -p 'test_*.py' -v` | 19测试通过、0失败、0跳过 |
| `node --test tests/webrtc.test.cjs` | 7测试通过、0失败、0跳过；使用模拟ICE，无STUN网络请求 |
| 全新目录安装后的完整测试 | 实际再次运行包校验、Python19项、JS7项，全部退出0；临时安装目录已清理 |
| skill-creator `quick_validate.py` | 实际运行，Skill is valid；仅入口结构验证 |
| `git diff --check` | 退出0 |
| `render-pf` → `pfctl -n -a skill.syntax.only -f <隔离文件>` | 退出0；仅语法，未加载/启停PF。pfctl仍显示通用-f提醒，-n明确不加载 |
| Mihomo v1.19.29 `-t -d <隔离目录> -f <合成JSON>` | 退出0、test is successful；手动selector、单GLOBAL和带代理组DoH。未启动核心、无TUN、无geodata依赖 |

Python测试实际覆盖：全新安装/已有安装不覆盖；中途写入异常保留部分产物且拒绝验收；缺依赖无自动安装；只读输入哈希保持；平台不符；相对/不存在/符号链接路径；损坏SQLite；WAL已提交数据一致快照；目录0700/文件0600；非root真实权限拒绝；日志时区与端口边界、缺文件/无匹配/损坏编码/PAC/后续未知状态；PF只生成；manifest路径逃逸/资源遗漏/JSON损坏；不存在的CLI参数拒绝；内部异常非零且不回显输入；离线工具禁止socket/Popen仍能完成。

部分安装异常是**合成故障注入**，权限拒绝是本机非root文件权限**实际测试**，两者不混写。上述网络禁止测试约束工具代码的socket/子进程，不是全机抓包或网络沙箱证明。

JS测试实际覆盖：API不可用、构造失败、候选分类/不返回原地址、观察超时、迟到offer不继续写已关闭peer、迟到reject被处理、即时协商失败关闭peer。结果不是Safari/Chrome真实行为验收。

## 七路线情景推演（walkthrough，不是生产执行）

每行按入口→前提→动作→停止/交付检查，未运行其生产操作。

| 场景 | 推演路径与结论 |
|---|---|
| R0：只确认当前出口，禁止修改 | G0登记read/network，无write；O3+O5只读证据；G5报告结束，不能进入修复 |
| R0：禁止联网 | 不执行O5、官方在线资料/STUN/clone；本地读取可交付，出口/当前在线兼容性未执行 |
| R1：首次空VPS | 先S0管理权限/身份，S1精确版本适配卡；无安装器证据则blocked，不套仓库中不存在的deploy |
| R1：已有面板，不同schema | 不重装，S2一致快照；无flow_override时不能写猜测列；S3受支持版本接口，否则blocked |
| R1：只有住宅代理账号 | G2拒绝服务器部署路线；R3只能保留卖家协议，不能试SSH或新增中转 |
| R2：官方回信后节点已恢复 | 原配置新请求通过后结束故障修改，保留历史证据、原因未确认；不能继续换端口求根因 |
| R2：中途实验失败/用户暂停 | 停依赖步骤；报告已完成/失败/未执行；仅清理预定临时PID，不自动回滚生产 |
| R3：已有Clash/禁止切默认 | 五层配置定位；副本校验；未授权重载不应用；其他节点GUI验收未执行 |
| R3：缺geodata且禁止联网 | O6停止真实配置校验，不下载备用资源或用简化配置冒充真实配置通过 |
| R4：配置已写但禁止关闭Claude | 完成configured后结束；启动采用/业务未执行，不为测试退出用户应用 |
| R4：CLI不存在/MDM接管 | 不把SDK当CLI，不绕管理策略；明确阻塞或在用户要求时仅预置 |
| R5：核心与浏览器同UID | render-pf拒绝；不放行全UID来取得成功，不加载模板 |
| R5：要求开机防护但未准备加载器 | 只能交付生成文件/语法证据；准备主机适配卡与隔离验证前不宣称active |
| R6：只授权GUI重启 | 保持selector，验证新启动、UDP/TCP与系统DNS；整机重启仍未执行 |
| 人工恢复 | 先新卡核对当前状态/可信备份及授权，再执行；安装器无force/自动删除/回滚 |

推演修正：让只读任务可不创建任务目录；保留条件负对照的失败与执行错误的区别；安装中途失败保留目录，不能重复覆盖；日志旧成功不能覆盖后续未知事件；运行卡未适配时停止而非替AI猜工具名。

## 未执行与明确能力边界

| 项目 | 状态 | 具体原因 |
|---|---|---|
| 新VPS真实安装/迁移、真实面板API/直接数据库修复 | 未执行 | 当前授权是改造技能，不干扰现有VPS；通用SQL写入已移除 |
| 生产Clash/应用切换、DNS泄漏、长连接、手机 | 未执行 | 用户现用网络保持不动；语法测试不替代实际业务 |
| 真实浏览器STUN/媒体、物理绕行/IPv6 | 未执行 | 用模拟ICE测试代码，无浏览器/系统操作 |
| PF加载器/LaunchDaemon/开机时序 | 未实现、未执行 | 现有仓库从未提供；本次明确模板边界，需独立主机适配与授权 |
| GUI或整机重启 | 未执行 | 本次不关闭现用软件、不改系统 |
| 第三方AI实际独立会话成功率 | 未执行 | 本次为作者逐路线推演及安装包验证，没有独立AI生产测试；不承诺任何AI必然成功 |
| 目标软件跨版本兼容 | 未全面验证 | 依赖实际版本源码/接口；无材料时停止，不推定兼容 |

## 提交与CI

已授权同步仓库：[qixian771-spec/vps-node-rebuild-3xui](https://github.com/qixian771-spec/vps-node-rebuild-3xui)。工作流 [Skill delivery validation](https://github.com/qixian771-spec/vps-node-rebuild-3xui/actions/workflows/validate.yml)。最终交付应核对实际提交SHA的运行，禁止拿其他提交的绿色状态代替。

提交前审阅公开文件：无真实节点配置/凭据、私人路径清单、原始日志、数据库/抓包或用户备份。快照/日志测试使用合成数据，隔离目录已按测试生命周期清理。证据记录只保留命令形式、退出码与脱敏结果。


### 已核对的提交与 CI 证据

- 实现提交：[10c9724c93e16d197303077d9eee1b98e105e168](https://github.com/qixian771-spec/vps-node-rebuild-3xui/commit/10c9724c93e16d197303077d9eee1b98e105e168)。推送后通过 `git ls-remote origin refs/heads/main` 回读，与本地SHA一致。
- 对应运行：[38314339485](https://github.com/qixian771-spec/vps-node-rebuild-3xui/actions/runs/38314339485)。`headSha` 精确等于上述提交，`status=completed`、`conclusion=success`。

| CI 环境 | 结果 |
|---|---|
| ubuntu-latest / Python3.10 / Node18 | success |
| ubuntu-latest / Python3.13 / Node18 | success |
| macos-latest / Python3.10 / Node18 | success |
| macos-latest / Python3.13 / Node18 | success |

这四组验证包结构、Python行为测试、JS合成测试和diff格式；不连接VPS、不加载PF、不运行真实Claude会话。记录CI结果的后续文档提交会再触发同一工作流，其本身状态以该提交的Checks为准；上表不是后续提交的替代证据。
