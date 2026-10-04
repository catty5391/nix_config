# NixOS 配置

这是一个适合公开托管的多主机 Flake。目前包含 `nas-linux`：NixOS 26.05、Niri、Noctalia、Home Manager 与模块化 Nixvim。

## 目录

```text
flake.nix                 # 输入、主机装配和 Home Manager 装配
hosts/nas-linux/          # 仅属于当前 NAS 的硬件、磁盘和网络配置
modules/nixos/            # 可复用的系统模块与服务
home/knight/              # knight 的桌面和应用配置
```

## 更新当前 NAS

```bash
sudo nixos-rebuild switch --flake /etc/nixos#nas-linux
```

旧的 `#nixos` 选择器暂时保留，方便迁移。

## 部署新机器

1. 复制 `hosts/nas-linux` 为一个新目录，例如 `hosts/laptop`。
2. 在新机器生成硬件配置，并替换新目录里的 `hardware-configuration.nix`。
3. 修改该主机的磁盘、CPU/GPU、显示器、代理和开放端口。
4. 在 `flake.nix` 的 `nixosConfigurations` 中增加新主机。
5. 安装或切换：

```bash
sudo nixos-rebuild switch --flake .#laptop
```

全新安装环境中使用 `nixos-install --flake .#laptop`。

## 凭据与脱敏策略

仓库不保存密码哈希、SSH 公钥、SSH 私钥、订阅文件或令牌。

- 系统账户使用 NixOS 的可变密码状态，安装后运行 `passwd` 和 `passwd knight`。
- SSH 公钥放到目标账户的 `~/.ssh/authorized_keys`，不要写入公开 Nix 文件。
- GitHub 私钥保持在 `~/.ssh/github`，仓库只声明 SSH 客户端如何引用它。
- `secrets/`、`private/`、私钥扩展名和 Nix 构建结果都已加入 `.gitignore`。

## 仅本机服务

### Telegram OpenList 同步服务

服务模块和脚本位于 `hosts/nas-linux`，仅由该主机导入并启用 `services.telegram-openlist-sync`。
服务使用 Nix 提供的 Python 标准库运行，由 systemd 管理，无需 pip 或虚拟环境。

在 NAS 上创建运行时环境文件（已有文件请直接编辑，不要覆盖）：

```bash
sudo install -m 600 -o root -g root hosts/nas-linux/telegram-openlist-sync/environment.example /etc/telegram-openlist-sync.env
sudoedit /etc/telegram-openlist-sync.env
```

必须填写 `TELEGRAM_BOT_TOKEN`、`ALLOWED_USER_ID`（个人数字 User ID）、
`OPENLIST_URL` 和 `OPENLIST_TOKEN`。可选项：`SCAN_PATH=/STRM`、
`SCAN_LIMIT=0`（不限速）、`SCAN_POLL_INTERVAL=2` 秒、`SCAN_TIMEOUT=3600` 秒。
环境文件使用 `KEY=value`，不要写 `export`；不会展开 `$VARIABLE` 或执行 shell。
服务不会继承交互式终端的环境变量。需要代理时在此文件填写 `https_proxy`，
并用 `no_proxy` 排除实际 OpenList 主机地址。
密钥文件不得加入 Git，也不要通过 `builtins.readFile`、Nix 路径值或 `environment.etc.*.text` 引入 store。
可将 `services.telegram-openlist-sync.environmentFile` 设置为其他运行时绝对路径字符串。

将新增源码纳入 Git 后，在仓库目录部署：

```bash
git add hosts/nas-linux/telegram-openlist-sync.nix hosts/nas-linux/telegram-openlist-sync hosts/nas-linux/default.nix README.md
sudo nixos-rebuild switch --flake .#nas-linux
systemctl status telegram-openlist-sync
journalctl -u telegram-openlist-sync -f
```

只接受白名单账户的私聊。启动后自动注册 Telegram 命令菜单：
`/download`、`/downloads`、`/refresh`、`/sync`、`/status`、`/help`、`/start`。
在私聊输入 `/` 或点击输入框旁的菜单按钮即可选择命令。
点击 `/download` 后会弹出回复输入框，粘贴链接发送即可；也可直接发送 `/download 链接`。
交互使用 [Telegram ForceReply](https://core.telegram.org/bots/api#forcereply)。
菜单注册失败每 5 分钟重试，不影响接收消息。

离线下载复用 OpenList 已配置的下载工具，无须给 bot 提供 115 Cookie。
在 `/etc/telegram-openlist-sync.env` 增加：

```ini
OFFLINE_DOWNLOAD_PATH="/115/离线下载"
OFFLINE_DOWNLOAD_TOOL="115 Cloud"
OFFLINE_POLL_INTERVAL=15
OFFLINE_TIMEOUT=86400
```

目录应为 **OpenList 内已存在、可写的目标目录**，不是 NAS 本地路径；请替换示例路径。
工具名必须与 OpenList 一致，例如 Cookie 驱动为 `115 Cloud`，开放平台驱动为 `115 Open`。
先在 OpenList 网页中确认该目录可以用选定工具离线下载，所需登录和临时目录均在 OpenList 配置。
`OFFLINE_DOWNLOAD_PATH` 留空时只关闭 bot 的下载提交，原有同步功能仍可用。

直接发送链接或 `/download 链接`，支持磁力、ed2k 和普通 HTTP(S) 下载直链。
`http://115cdn/`（以及 HTTPS 形式）暂不支持，bot 会明确提示并拒绝整条消息中的链接。
每行一条，每次最多 20 条；保留大小写、签名参数，批内去重，并跳过正在跟踪的相同链接。
网页分享链接不会自动提取密码或转存，HTTP 链接能否下载取决于 OpenList 工具。
bot 调用 `/api/fs/add_offline_download`，逐条报告提交结果；提交超时不自动重试，
因为服务端可能已接收，请先检查 OpenList 后台。采用 `delete_never` 保留下载工具临时文件。

任务 ID 持久化到服务状态目录，重启后继续通过 `/api/task/offline_download/info` 跟踪。
下载完成后自动调用 `/api/fs/list`（`refresh=true`）刷新该任务的目标目录。
也可点击命令菜单中的 `/refresh`，手动刷新 `OFFLINE_DOWNLOAD_PATH` 配置的目录。
刷新不递归处理子目录，也不会启动 STRM 扫描；需要扫描时使用 `/sync`。
刷新失败会明确提示，可用 `/refresh` 重试，不会重新提交下载任务。
`/downloads` 显示配置及跟踪数量，`/status` 仍查询扫描状态。
监控超时只停止跟踪，不取消下载；失败详情在 OpenList 后台查看。
提交成功与本地保存之间若进程崩溃，可能遗漏跟踪；后台任务仍由 OpenList 运行。
接口与参数依据 [OpenList 官方实现](https://github.com/OpenListTeam/OpenList/blob/main/server/handles/offline_download.go)，
协议支持取决于安装的 OpenList 版本及选用的下载工具。

扫描在后台监控，重复命令不会启动第二个本地任务；超时只结束监控，不取消 OpenList 扫描。
重启后可以用 `/status` 查询已有扫描，但不会自动恢复完成通知。
更新游标保存在 `/var/lib/telegram-openlist-sync`，先保存再执行，避免重启重放命令；
极端情况下保存后立即崩溃会丢失该条命令，需要重新发送。
修改环境文件后执行 `sudo systemctl restart telegram-openlist-sync`。
环境文件缺失会导致服务启动失败；无须开放入站端口。

OpenList 需支持原脚本使用的 `/api/admin/scan/start` 与 `/api/admin/scan/progress`，
并返回 `code=200` 和布尔型 `data.is_done`。部署前确认目标版本支持这些接口。
Telegram 使用长轮询，同一 Bot 不应同时运行其他轮询实例，且不能配置 webhook
（参见 [Telegram 官方说明](https://core.telegram.org/bots/faq#how-do-i-get-updates)）。

qBittorrent 不属于此 Flake。NAS 上的程序、systemd 服务、Web UI 配置和密码均作为本机状态单独维护，不会被 NixOS 重建，也不会复制到其他主机。

磁盘 UUID 仍位于 `hosts/nas-linux`。它们用于准确挂载本机磁盘，不是认证凭据，也不能用来远程访问机器；换机器时必须重新生成或修改。

发布前可执行：

```bash
rg -n '(hashedPassword|Password_PBKDF2|ssh-(rsa|ed25519)|BEGIN .*PRIVATE KEY|api[_-]?key|token)' .
```

正常结果只应包含本说明中的检查命令和注释，不应包含真实值。
