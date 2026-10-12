# 安装与首次使用

## 支持范围与依赖分离

| 层 | 支持/最低依赖 | 不包含 |
|---|---|---|
| 技能阅读 | 能读取 Markdown 与相对引用的 AI 环境 | 不保证第三方 AI 的自动发现机制 |
| 随包工具 | macOS/Linux，Python 3.10+ 标准库 | 无 pip/npm 安装、无网络、无 root 要求 |
| 开发测试 | Python 3.10+、Node 18+；Git/gh 仅用于提交/CI查询 | 不依赖真实节点或账号 |
| 服务端路线 | 经检测的 Linux、实际版本 3x-ui/Xray、SSH/系统管理工具 | 不捆绑目标二进制，不保证所有 fork schema |
| 客户端路线 | 实际安装的 Mihomo 和 GUI、对应版本配置/API契约 | 不捆绑 Clash、不修改自动更新 |
| Mac 防护 | macOS、已核验的浏览器/系统工具；PF写入另需权限 | 无 Windows PF方案、无自动开机加载器 |

Python/macOS/Linux 支持表示工具设计与 CI 测试范围，不代表所有 OS 发行版的生产部署已验收。最新真实测试范围见仓库交付记录。

## 新安装（源码与离线包相同）

1. 已有本地完整目录时直接从第2步开始。用户允许下载才从**指定仓库**获取；已有同名目录不重 clone、不覆盖、不改来源：

```sh
git clone https://github.com/qixian771-spec/vps-node-rebuild-3xui.git "$SOURCE_DIR"
```

`SOURCE_DIR` 是用户允许的绝对新目录，父目录已存在。退出 0 后记录 `git -C "$SOURCE_DIR" rev-parse HEAD`；联网失败停止。下载最新仓库不等于已审核供应链，版本来源按本次任务记录。

2. 在实际源码根运行（`SKILL_SOURCE` 是 `pwd -P` 返回的绝对路径）：

```sh
python3 --version
python3 "$SKILL_SOURCE/scripts/skillctl.py" validate --root "$SKILL_SOURCE"
```

要求 Python≥3.10、validate退出0，JSON `status=passed`。文件缺失/链接断裂停止，不从网上逐个补资源。

3. 安装目录是 AI 工具允许的技能目录下 `vps-node-rebuild-3xui`。Codex 常见用户目录为 `${CODEX_HOME:-$HOME/.codex}/skills`，先核对该工具当前配置；不能认为所有AI都是这个路径。用户授权安装时可创建这个已确认的**父目录**，不能覆盖技能子目录。

```sh
python3 "$SKILL_SOURCE/scripts/skillctl.py" install --source "$SKILL_SOURCE" --destination "$SKILL_DESTINATION"
python3 "$SKILL_DESTINATION/scripts/skillctl.py" validate --root "$SKILL_DESTINATION"
python3 "$SKILL_DESTINATION/scripts/skillctl.py" --help
```

父目录须存在、路径为绝对且无符号链接；每条退出0才继续。工具仅复制 manifest 明确列出的文件，整个目录0700、文件0600，不要求可执行位（通过Python调用）。所有入口引用、手册、资产/JS、合成测试及LICENSE随包复制，不复制 .git、原始日志或用户工作文件。

4. 在 AI 中显式请求“读取安装目录中的 SKILL.md，按 R0 检查一个提供的合成任务，不联网、不写目标配置”。能读取入口及其相对引用是本地安装验证；AI是否在新会话自动发现技能需在该产品中单独观察。未观察就标未执行。

## 已有安装与部分安装

- `install` 拒绝已有目的目录（退出3），没有 `--force` 或自动合并参数。
- 更新：先记录当前安装版本/本地改动；在同一父目录的新版本目录中安装并验收。只有已有授权明确包括替换时，单独建立替换卡（旧目录私有备份、目标工具指向、文件所有权、验证及人工恢复方式）；本包不自动重命名/删除旧安装，也不替工具选择新位置。
- 安装中途失败：目的目录可能只完成部分文件，保留并记录错误，`validate` 必须失败。禁止把部分目录交付为可用或在其上重复安装。新一次安装使用经授权的新空目录；删除部分产物是独立授权动作。
- 离线包：复制 manifest 列出的完整目录后运行同样 validate/install；不执行 clone/在线资料核验/STUN。缺目标依赖就交付阻塞，不下载备用实现。

## 首次执行与权限

先从 [执行手册 G0](runbook.md) 开始，准备目标、约束、已有授权、必要输入、来源证明及已确认的真实路径。技能安装不授予 SSH、root、浏览器控制、关闭软件或发布权限。

日常命令和退出码见 [操作契约 O1](operations.md)。依赖检查只证明存在性；生产版号、监听、schema和API都要另查。只读任务不用sudo来“修好”不足的读取能力；写特权文件必须在本次授权内。凭据通过目标工具的安全输入/受限文件取得，不放在提示示例、进程参数或版本库。

Windows 可阅读文档，但随包执行工具、PF和本次CI未覆盖Windows；不得将macOS命令机械改路径后宣称支持。
