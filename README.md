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

## Shell 目录跳转

共享的 `modules/nixos/zsh.nix` 通过 NixOS 的 `programs.zoxide` 初始化 Zsh，适用于 `msi` 和 `nas-linux`。
重建对应主机后打开新终端，或执行 `exec zsh`。先用 `cd` 访问目录，zoxide 会自动记录：

- `z nix_config`：按关键词跳到已记录的目录。
- `z nix config`：用多个关键词匹配路径。
- `zi`：通过已有的 fzf 交互选择目录。
- `z -`：返回上一个目录。

保留原生 `cd`；各用户的访问记录独立保存。

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
`OPENLIST_URL` 和 `OPENLIST_TOKEN`。可选项：`SCAN_PATH=/strm`（须与 OpenList 挂载路径大小写一致）、
`SCAN_LIMIT=0`（不限速）、`SCAN_POLL_INTERVAL=15` 秒、`SCAN_TIMEOUT=3600` 秒。
`OPENLIST_SCAN_ENABLED=false` 默认关闭 `/sync` 全量扫描，因为 bot 无法限制服务端扫描的实际网盘请求速度；
确需使用时显式设为 `true`，并按服务端扫描实现配置 `SCAN_LIMIT`。
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
`/download`、`/downloads`、`/strm`、`/refresh`、`/cancel_refresh`、`/sync`、`/status`、`/reset`、`/help`、`/start`。
在私聊输入 `/` 或点击输入框旁的菜单按钮即可选择命令。
点击 `/download` 后会弹出回复输入框，粘贴链接发送即可；也可直接发送 `/download 链接`。
发送 `/strm` 会读取 `SCAN_PATH`（默认 `/strm`）下的直接子文件夹，按 OpenList 返回的修改时间倒序编号；
选中某个编号只刷新该 STRM 文件夹及其子目录，不递归整个 STRM 根目录。
手动列表和刷新独立于 `OFFLINE_DOWNLOAD_PATH`；下载完成后的自动刷新从任务对应的 offline 目标目录选择最新子目录。
每页显示 10 个文件夹，通过消息下方“上一页 / 下一页”按钮翻页，编号跨页连续。
再发送 `/refresh 编号`，即可递归刷新该编号文件夹及其子目录（例如第二页的 `/refresh 11`）。
支持 `/refresh 1 3 5` 或 `/refresh 1,3,5`，空格及中英文逗号均可分隔，重复序号自动去重，按输入顺序依次刷新。
每批最多选择 5 个文件夹；必须填写序号，不支持空输入、范围或路径。
格式错误、越界、超过数量限制或列表过期都会整批拒绝，不会部分执行，也不会退回刷新整个下载目录。
手动和自动刷新共用一把锁，每次只运行一批；自动刷新等待当前批次结束，手动操作在忙碌时提示稍后再试。
取消按钮会停止整批后续目录，某个目录请求失败时也会停止该批次。
执行每批手动刷新时，先对 STRM 根目录调用一次 `/api/fs/list`（`refresh=true`），只更新这一层列表；
随后按原来的序号对应路径刷新所选子目录，不重新排列编号，也不递归根目录下的其他文件夹。
这次父目录刷新计入整批目录数量上限；父目录刷新失败或取消时不继续子目录。
列表 15 分钟有效，翻页沿用同一份排序结果；发送 `/strm` 重新获取后旧按钮失效。
浏览 `/strm` 不强制绕过 OpenList 缓存，bot 自身也缓存列表 5 分钟；浏览结果可能暂未包含新增目录。
显式刷新仍强制更新，但同一路径默认至少间隔 5 分钟，未到时间时等待，取消和 Reset 仍可用。
超长文件夹名会在列表中缩略显示，刷新仍使用完整路径。
交互使用 [Telegram ForceReply](https://core.telegram.org/bots/api#forcereply)。
菜单注册失败每 5 分钟重试，不影响接收消息。

帮助页和 STRM 列表下方提供 **Reset bot** 按钮，也可发送 `/reset`。
仅白名单用户私聊可重置。bot 退出后由 systemd 约 10 秒后重新拉起，清除内存中的分页和卡住的线程，
已保存的下载任务继续跟踪；等待中的命令需重新发送，旧 Reset 按钮失效。
普通操作在有上限的后台队列中执行，目录请求卡住时仍能接收重置操作。
重置不会重启 NAS，也不会取消 OpenList 已接收的任务；若在提交链接时重置，请先在 OpenList 后台确认结果再重发。
NAS 整机死机或无法连接 Telegram 时，聊天按钮无法恢复连接，需通过主机管理入口处理。

手动刷新和下载完成后的自动刷新都会发送“取消本次刷新”按钮；按钮只取消对应任务，过期按钮不会影响新任务。
`/cancel_refresh` 会取消当前私聊正在执行的所有目录刷新，操作绕过普通队列。
取消后，已发出的 OpenList 请求需等返回或超时，随后停止后续分页和递归并报告已刷新目录数；
刷新线程退出时释放锁，之后可以重新刷新。已完成的刷新保留，下载和 `/sync` 扫描不受影响。
自动刷新被取消后不会再次自动重试该已完成下载任务的刷新。

消息展示逻辑集中在 `hosts/nas-linux/telegram-openlist-sync/ui/`：统一状态图标、标题和分段，
目录修改时间显示为北京时间，STRM 列表每页 10 个，其他超长消息自动分条发送。
使用纯文本排版，文件名中的特殊字符不会被当作 HTML 或 Markdown。
新增该目录后也须纳入 Git，再执行 flake rebuild，确保 Nix 打包时包含它。

离线下载复用 OpenList 已配置的下载工具，无须给 bot 提供 115 Cookie。
在 `/etc/telegram-openlist-sync.env` 增加：

```ini
OFFLINE_DOWNLOAD_PATH="/115/离线下载"
OFFLINE_DOWNLOAD_TOOL="115 Cloud"
OFFLINE_POLL_INTERVAL=60
OFFLINE_TIMEOUT=86400
OFFLINE_MAX_ACTIVE_DOWNLOADS=1
```

目录应为 **OpenList 内已存在、可写的目标目录**，不是 NAS 本地路径；请替换示例路径。
工具名必须与 OpenList 一致，例如 Cookie 驱动为 `115 Cloud`，开放平台驱动为 `115 Open`。
先在 OpenList 网页中确认该目录可以用选定工具离线下载，所需登录和临时目录均在 OpenList 配置。
`OFFLINE_DOWNLOAD_PATH` 留空时只关闭 bot 的下载提交，原有同步功能仍可用。

直接发送链接或 `/download 链接`，支持磁力、ed2k 和普通 HTTP(S) 下载直链。
`http://115cdn/`（以及 HTTPS 形式）暂不支持，bot 会明确提示并拒绝整条消息中的链接。
每行一条，每次最多 20 条；保留大小写、签名参数，批内去重，并跳过正在跟踪的相同链接。
默认最多同时跟踪 1 个未结束下载，后续链接在内存中等待空位再提交，提交请求至少间隔 60 秒。
批次仍在提交时会继续查询已接收任务，避免等待空位时卡住。
重启只恢复已保存的任务，尚未提交的链接不会恢复；重发前先核对后台，避免重复添加。
网页分享链接不会自动提取密码或转存，HTTP 链接能否下载取决于 OpenList 工具。
bot 调用 `/api/fs/add_offline_download`，逐条报告提交结果；提交超时不自动重试，
因为服务端可能已接收，请先检查 OpenList 后台。采用 `delete_never` 保留下载工具临时文件。

任务 ID、批次及各任务完成状态持久化到服务状态目录，重启后继续通过 `/api/task/offline_download/info` 跟踪。
同一条消息提交的链接属于一批；等该批所有已跟踪任务成功、失败、取消或监控超时后，统一进行一次自动刷新。
按成功链接数 N 选择最新的 N 个子目录（最多 20 个），重复跳过、提交未确认及未成功的链接不增加数量。
同一链接返回多个任务 ID 时只算一条，且须所有关联任务成功；旧状态文件没有批次信息的任务继续按单条处理。
目前 OpenList 的离线提交和任务详情均返回 `TaskInfo`，没有具体下载结果路径；任务名称中的路径也是提交时的目标目录，不能视为新下载文件夹。
依据 [任务响应定义](https://github.com/OpenListTeam/OpenList/blob/main/server/handles/task.go) 和
[下载任务名称实现](https://github.com/OpenListTeam/OpenList/blob/main/internal/offline_download/tool/download.go)，
bot 在一批任务结束后先更新该批目标目录的直接列表，再按修改时间倒序选择最新的 N 个子目录，依次递归刷新。
例如目标目录为 `/115网盘/media/strm`，同批 3 条链接均成功，就刷新该目录列表后，再刷新其中最新的 3 个子目录。
父目录每批只强制更新一次，整批共用递归数量上限和取消按钮；可选子目录不足 N 个时按实际数量刷新并提示。
bot 会显示选中的路径并标注这是按时间推测的结果；多个任务同时完成时，最新目录不一定属于当前任务。
没有子目录或无法得到有效修改时间时，只更新父目录列表并提示，不任意选择目录。查找目录及后续递归均支持取消。
手动刷新需先用 `/strm` 获取序号，再发送 `/refresh 序号`，空命令仅显示使用提示。
`OFFLINE_REFRESH_RECURSIVE=true` 默认开启，控制手动所选文件夹及自动选中的最新子目录的递归；手动每批最多 5 个的限制保持不变。
`OFFLINE_REFRESH_MAX_DIRS=100` 限制单次最多刷新目录数，批量手动刷新共享这一总上限，自动刷新时包含父目录列表更新。
`OFFLINE_REFRESH_MAX_DEPTH=6` 限制所选目录下的递归深度（所选目录为 0），`OPENLIST_REFRESH_REQUEST_BUDGET=200` 限制整批目录读取次数，包含分页。
达到任一上限会提示未完成递归。每个目录会分页读取其子目录，文件本身不需要单独调用刷新接口。
设为 `OFFLINE_REFRESH_RECURSIVE=false` 时只更新所选目录这一层，不会启动 STRM 扫描。
刷新失败会明确提示，可用 `/refresh 序号` 重试，不会重新提交下载任务。
`/downloads` 在本地显示配置、跟踪数量、同时下载上限、目录请求间隔及剩余冷却时间，不调用 OpenList；`/status` 仍查询扫描状态。
监控超时只停止跟踪，不取消下载；失败详情在 OpenList 后台查看。
提交成功与本地保存之间若进程崩溃，可能遗漏跟踪；后台任务仍由 OpenList 运行。
接口与参数依据 [OpenList 官方实现](https://github.com/OpenListTeam/OpenList/blob/main/server/handles/offline_download.go)，
协议支持取决于安装的 OpenList 版本及选用的下载工具。

所有 bot 发出的 OpenList 请求统一串行限速，默认全局间隔 `OPENLIST_REQUEST_INTERVAL=10` 秒，
目录列表间隔 `OPENLIST_LIST_INTERVAL=30` 秒，提交间隔 `OPENLIST_SUBMIT_INTERVAL=60` 秒。
同一路径强制刷新间隔为 `OPENLIST_PATH_REFRESH_INTERVAL=300` 秒，本地列表缓存有效期为 `OPENLIST_LIST_CACHE_TTL=300` 秒。
这些时间均为正数，间隔从上一次对应请求完成后计算，限速等待支持取消刷新和 Reset。
HTTP 403/429、接口或任务中的风控/验证码/频繁请求提示，会触发 `OPENLIST_RISK_COOLDOWN=1800` 秒冷却；
普通请求错误按 `OPENLIST_ERROR_BACKOFF=30` 秒指数退避，最高 900 秒，并遵守更长的 HTTP `Retry-After`。
冷却保存在服务状态目录的 `openlist-request-state.json`，重启或 Reset 不会清除。
自动刷新遇到这类错误会保留成功下载记录，冷却后再尝试；手动刷新停止并提示，下载提交失败则停止剩余提交，绝不自动重试写请求。

以上是降低请求压力的保守默认值，不是 115 保证安全的频率。OpenList 的
[下载任务实现](https://github.com/OpenListTeam/OpenList/blob/main/internal/offline_download/tool/download.go)
会自行轮询下载状态，bot 限速不会改变其内部轮询，也不会停止网页、其他客户端或已有扫描产生的请求。
默认限制同时下载数量，是为了减少 bot 新增的后台轮询任务；既有 OpenList 任务仍需在后台管理。
更新时请核对旧环境文件：显式设置的 `OFFLINE_POLL_INTERVAL=15`、`OFFLINE_REFRESH_MAX_DIRS=10000` 等值会覆盖新默认值。
按 `environment.example` 调整非敏感配置即可，不要覆盖原有 Token 和目录配置。

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
