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

qBittorrent 不属于此 Flake。NAS 上的程序、systemd 服务、Web UI 配置和密码均作为本机状态单独维护，不会被 NixOS 重建，也不会复制到其他主机。

磁盘 UUID 仍位于 `hosts/nas-linux`。它们用于准确挂载本机磁盘，不是认证凭据，也不能用来远程访问机器；换机器时必须重新生成或修改。

发布前可执行：

```bash
rg -n '(hashedPassword|Password_PBKDF2|ssh-(rsa|ed25519)|BEGIN .*PRIVATE KEY|api[_-]?key|token)' .
```

正常结果只应包含本说明中的检查命令和注释，不应包含真实值。
