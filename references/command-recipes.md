# 条件命令补充

完整执行入口在 [runbook](runbook.md)，真实工具参数/退出码在 [operations](operations.md)。这里仅保留服务器可选操作。不是按顺序执行的安装脚本。

## BBR：只应用目标文件

前提：服务端R1明确包含BBR，已确认Linux内核、权限和当前设置；在目标服务器执行：

```sh
sysctl -n net.ipv4.tcp_available_congestion_control
sysctl -n net.ipv4.tcp_congestion_control
sysctl -n net.core.default_qdisc
```

每条0才解读值。若bbr已可用不加载模块；未可用且已核实该主机可加载tcp_bbr时才执行一次 `modprobe tcp_bbr`。失败停止加载项，不偷偷忽略；已有只读结果可记录，但不能把加载失败标成功。

写前要求 `/etc/sysctl.d/99-node-bbr.conf` 不存在；存在时停止这份“首次创建”示例，另外准备备份与最小编辑卡，不能覆盖。下面单条创建用Python的独占写入，在root授权会话执行：

```sh
python3 - <<'PY'
from pathlib import Path
p = Path('/etc/sysctl.d/99-node-bbr.conf')
with p.open('x') as f:
    f.write('net.core.default_qdisc=fq\nnet.ipv4.tcp_congestion_control=bbr\n')
PY
```

0代表文件创建；非零停止。随后**只应用本文件**：

```sh
sysctl -p /etc/sysctl.d/99-node-bbr.conf
sysctl -n net.ipv4.tcp_congestion_control
sysctl -n net.core.default_qdisc
```

逐条0、回读bbr/fq才标当前生效；失败可能已部分修改，报告已修改键，不自动恢复猜测的默认值。模块启动持久化需要单独核实该平台加载机制；未重启不能记开机验收通过。禁止用 `sysctl --system` 应用全部无关配置。

## 私有管理 SSH 隧道

前提：用户已选择私有管理，服务器loopback面板及原管理入口已验证；SSH_ALIAS、LOCAL_PORT、PANEL_PORT分别来自已校验SSH配置、空闲本机端口和实际面板监听。工作目录本机私有任务目录：

```sh
ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=6 \
  -L "127.0.0.1:$LOCAL_PORT:127.0.0.1:$PANEL_PORT" "$SSH_ALIAS"
```

前台进程无输出且持续运行不是充分证据；确认本机仅loopback监听、隧道内面板正常并且服务器公网暴露检查符合任务。SSH 255为连接/认证/转发错误，其他非零停止；不改用公网明文面板。记录该进程PID，结束时只终止它并确认监听消失；常驻服务不在这个一次性命令的能力内。

## 已撤除的高风险示例

- 直接SQL修改flow：不同schema/生成模型不兼容；改用 [服务端S2–S3](server.md) 的实际版本受支持接口。
- 自动抓取登录JS再猜API：旧管道可能隐藏失败；现在要求适配卡、明确版本接口、失败即停。
- 猜测路径的Claude日志扫描：由 [O8](operations.md) 单路径有界筛选替代。

这是能力边界，不是通过失败后自动换接口完成任务的授权。
