{
  config,
  inputs,
  pkgs,
  ...
}: let
  upstream = inputs.nyxniri;
  homeDirectory = config.home.homeDirectory;

  # NyxNiri's deployer normally replaces /home/user. Do the same purely at
  # evaluation time, and point the wallpaper browser at the existing library.
  noctaliaConfig = builtins.replaceStrings
    [
      "/home/user/图片/Wallpapers"
      "/home/user"
      ''[widget."ray/echolyrics:echolyrics"]
capsule = false
''
      ''[theme.templates]
builtin_ids = ["kitty", "qt", "starship"]''
      ''post_hook = "if pgrep -x fcitx5 >/dev/null 2>&1; then pkill -x fcitx5; sleep 1; fcitx5 -d >/dev/null 2>&1 & fi"''
      ''behavior_order = [ "lock", "screen-off", "lock-and-suspend" ]''
      "    [idle.behavior.lock-and-suspend]\n    action = \"lock_and_suspend\"\n    enabled = true\n    timeout = 900.0\n"
    ]
    [
      "${homeDirectory}/.config/wallpaper"
      homeDirectory
      ""
      ''[theme.templates]
enable_builtin_templates = false
builtin_ids = []''
      "# Fcitx is managed by Home Manager; do not restart it from a theme hook."
      ''behavior_order = [ "lock", "screen-off" ]''
      ""
    ]
    (builtins.readFile "${upstream}/configs/noctalia/noctalia-config.toml");
in {
  programs.noctalia = {
    enable = true;
    systemd.enable = true;
  };

  home.packages = with pkgs; [
    adw-gtk3
    dconf
    ffmpeg
    glib
    inotify-tools
    jq
    mpvpaper
  ];

  xdg.configFile = {
    "noctalia/config.toml".text = noctaliaConfig;
    "noctalia/theme-sync.sh" = {
      # Upstream's cleanup regex also matches an explanatory comment in its
      # own GTK4 template and deletes the freshly rendered file. Narrow the
      # legacy marker check while preserving the rest of the script verbatim.
      text = builtins.replaceStrings
        [
          "#!/usr/bin/env bash"
          ''libadwaita\.css|noctalia\.css|iNiR theming''
        ]
        [
          "#!${pkgs.bash}/bin/bash"
          ''noctalia\.css|iNiR theming''
        ]
        (builtins.readFile "${upstream}/configs/noctalia/theme-sync.sh");
      executable = true;
    };
    "noctalia/wallpaper-hook.sh" = {
      text = builtins.replaceStrings
        ["#!/bin/bash"]
        ["#!${pkgs.bash}/bin/bash"]
        (builtins.readFile "${upstream}/configs/noctalia/wallpaper-hook.sh");
      executable = true;
    };
    "noctalia/mpvpaper-sync.sh" = {
      text = builtins.replaceStrings
        ["#!/bin/bash"]
        ["#!${pkgs.bash}/bin/bash"]
        (builtins.readFile "${upstream}/configs/noctalia/mpvpaper-sync.sh");
      executable = true;
    };
    "noctalia/mpv-hook.lua".source = "${upstream}/configs/noctalia/mpv-hook.lua";
    "noctalia/templates" = {
      source = "${upstream}/configs/noctalia/templates";
      recursive = true;
    };
    "wallpaper/lawson_fuji.webp".source = "${upstream}/assets/wallpapers/lawson_fuji.webp";
  };

  xdg.dataFile = {
    "fcitx5/themes/nyxmellow/templates" = {
      source = "${upstream}/assets/fcitx5/nyxmellow/templates";
      recursive = true;
    };
    "noctalia/plugins/mpvpaper" = {
      source = "${inputs.noctalia-plugins}/mpvpaper";
      recursive = true;
    };
  };
}
