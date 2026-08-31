{
  lib,
  pkgs,
  username,
  ...
}: {
  nix.settings = {
    experimental-features = ["nix-command" "flakes"];
    substituters = [
      "https://mirrors.ustc.edu.cn/nix-channels/store?priority=10"
      "https://cache.nixos.org/?priority=40"
    ];
    trusted-users = ["root" username];
  };

  nixpkgs.config.allowUnfree = true;
  users.mutableUsers = true;
  users.users.${username} = {
    description = username;
    isNormalUser = true;
    home = "/home/${username}";
    ignoreShellProgramCheck = true;
    extraGroups = [
      "wheel"
      "render"
      "networkmanager"
      "audio"
      "input"
      "video"
      "docker"
      "kvm"
      "libvirtd"
      "i2c"
    ];
  };

  # wheel用户组sudo免密
  security.sudo.wheelNeedsPassword = false;

  # Passwords and authorized keys intentionally remain local mutable state.
  # Set them with passwd and ~/.ssh/authorized_keys after installation.

  environment.systemPackages = with pkgs; [
    zellij
    p7zip
    wineWow64Packages.stable
    winetricks
    google-chrome
    pulseaudio
    pciutils
    ffmpeg
    libva
    libva-utils
    power-profiles-daemon
    git
    curl
    wget
    bluez
    cachix
    mdadm
    lvm2
    btrfs-progs
    smartmontools
    codex
  ];

  environment.sessionVariables = {
    NIXOS_OZONE_WL = "1";
    TERMINAL = "kitty";
    QT_IM_MODULE = "fcitx";
    QT5_IM_MODULE = "fcitx";
    XMODIFIERS = "@im=fcitx";
  };

  services.udisks2.enable = true;
  systemd.sleep.settings.Sleep = {
    AllowSuspend = "no";
    AllowHibernation = "no";
    AllowHybridSleep = "no";
    AllowSuspendThenHibernate = "no";
  };

  time.timeZone = "Asia/Shanghai";
  i18n.defaultLocale = "en_US.UTF-8";
  i18n.extraLocaleSettings = {
    LC_TIME = "zh_CN.UTF-8";
    LC_MEASUREMENT = "zh_CN.UTF-8";
    LC_NUMERIC = "zh_CN.UTF-8";
    LC_PAPER = "zh_CN.UTF-8";
    LC_CTYPE = "zh_CN.UTF-8";
  };

  console = {
    font = "Lat2-Terminus16";
    keyMap = lib.mkDefault "us";
    useXkbConfig = true;
  };

  boot.loader.grub.configurationLimit = 3;
  nix.gc = {
    automatic = lib.mkDefault true;
    dates = lib.mkDefault "weekly";
    options = lib.mkDefault "--delete-older-than 7d";
  };
}
