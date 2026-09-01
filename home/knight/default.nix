{
  config,
  pkgs,
  lib,
  ...
}: let
  mediaPlayers = [
    "mpv.desktop"
    "vlc.desktop"
  ];
in {
  imports = [
    ./programs
    ./terminal
    ./niri
    ./noctalia
    ./fcitx5
    ./rofi
    ./wallpaper
    ./music
    ./ssh
    ./apps
    ./sessionPath.nix
  ];

  home.packages = with pkgs; [
    xwayland-satellite # xwayland support
    libnotify
  ];

  # 自动创建截图文件夹
  home.activation.ensureScreenshotDir = lib.hm.dag.entryAfter ["writeBoundary"] ''
    mkdir -p "${config.home.homeDirectory}/screenshot"
  '';

  # Noctalia v5 provides the polkit agent, notification center and idle logic.
  services.polkit-gnome.enable = false;

  # 消息通知
  services.swaync.enable = false;
  services.swayidle.enable = false;
  catppuccin.swaync = {
    enable = true;
    flavor = "mocha";
  };

  # services.mako.enable = true;
  # catppuccin.mako = {
  #   enable = true;
  #   accent = "mauve";
  #   flavor = "mocha";
  # };

  xdg.mimeApps.enable = true;
  xdg.mimeApps.defaultApplications = {
    "image/png" = ["imv.desktop"];
    "image/jpeg" = ["imv.desktop"];
    "image/gif" = ["imv.desktop"];
    "audio/aac" = mediaPlayers;
    "audio/flac" = mediaPlayers;
    "audio/mp4" = mediaPlayers;
    "audio/mpeg" = mediaPlayers;
    "audio/ogg" = mediaPlayers;
    "audio/opus" = mediaPlayers;
    "audio/webm" = mediaPlayers;
    "audio/x-m4a" = mediaPlayers;
    "audio/x-ms-wma" = mediaPlayers;
    "audio/x-wav" = mediaPlayers;
    "video/3gpp" = mediaPlayers;
    "video/3gpp2" = mediaPlayers;
    "video/mp2t" = mediaPlayers;
    "video/mp4" = mediaPlayers;
    "video/mpeg" = mediaPlayers;
    "video/ogg" = mediaPlayers;
    "video/quicktime" = mediaPlayers;
    "video/webm" = mediaPlayers;
    "video/x-flv" = mediaPlayers;
    "video/x-matroska" = mediaPlayers;
    "video/x-msvideo" = mediaPlayers;
    "text/html" = "google-chrome.desktop";
    "x-scheme-handler/http" = "google-chrome.desktop";
    "x-scheme-handler/https" = "google-chrome.desktop";
    "x-scheme-handler/termius" = "termius-app.desktop";
  };

  # 光标配置
  home.pointerCursor = {
    enable = true;
    package = pkgs.adwaita-icon-theme;
    name = "Adwaita";
    size = 24;
  };

  home.sessionVariables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
    LANG = "en_US.UTF-8"; # 系统主语言英文
    LC_CTYPE = "zh_CN.UTF-8"; # 字符显示支持中文
    LC_MESSAGES = "en_US.UTF-8"; # 程序输出信息保持英文
  };

  home.stateVersion = "26.05";
  # home.enableNixpkgsReleaseCheck = false;
}
