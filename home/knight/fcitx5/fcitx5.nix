{
  pkgs,
  inputs,
  ...
}: let
  # 给 fcitx5-rime 注入雾凇拼音数据
  fcitx5-rime-ice = pkgs.fcitx5-rime.override {
    rimeDataPkgs = [
      pkgs.rime-data
      pkgs.rime-ice
    ];
  };
in {
  i18n.inputMethod = {
    type = "fcitx5";
    enable = true;

    fcitx5 = {
      waylandFrontend = true;

      addons = with pkgs; [
        fcitx5-rime-ice

        qt6Packages.fcitx5-configtool

        # 如果你只用 Rime，这个其实可以删除
	qt6Packages.fcitx5-chinese-addons
      ];

      # 输入法排序
      settings.inputMethod = {
        GroupOrder."0" = "Default";

        "Groups/0" = {
          Name = "Default";
          "Default Layout" = "us";

          # 如果希望默认使用 Rime：
          DefaultIM = "rime";
        };

        "Groups/0/Items/0".Name = "rime";
        "Groups/0/Items/1".Name = "keyboard-us";
      };

      settings = {
        globalOptions = {
          "Hotkey/TriggerKeys" = {
            "0" = "Super+space";
          };
        };

        addons = {
          classicui.globalSection = {
            # Candlelight 主题
            Theme = "macOS-light";

            # 候选框字号
            Font = "Noto Sans CJK SC 18";
            MenuFont = "Noto Sans CJK SC 18";

            # 根据屏幕 DPI 缩放
            PerScreenDPI = "True";

            # 横向候选列表
            "Vertical Candidate List" = "False";
          };

          # 可选：
          # 让预编辑文字显示在应用程序内部
          rime.globalSection = {
            PreeditInApplication = "True";
          };
        };
      };
    };
  };

  # 安装 Candlelight 主题
  xdg.dataFile."fcitx5/themes/macOS-light".source =
    "${inputs.fcitx5-candlelight}/macOS-light";

  # Home Manager already starts fcitx5-daemon.service. Mask the package's XDG
  # autostart entry so Niri does not launch a competing second instance.
  xdg.configFile."autostart/org.fcitx.Fcitx5.desktop".text = ''
    [Desktop Entry]
    Type=Application
    Name=Fcitx 5
    Hidden=true
  '';

  # 启用 nixpkgs 中的 rime-ice 默认配置
  #
  # nixpkgs 会把 rime-ice 上游的 default.yaml
  # 改名为 rime_ice_suggestion.yaml，
  # 所以需要显式 include。
  xdg.dataFile."fcitx5/rime/default.custom.yaml".text = ''
    patch:
      __include: rime_ice_suggestion:/
  '';

  # Candlelight 已经作为主主题的话，这部分可以直接删除。
  #
  # 如果你以后还想保留 Catppuccin 主题文件，
  # enable=true + apply=false 也可以保留，不会自动覆盖 Theme。
  #
  # catppuccin.fcitx5 = {
  #   enable = true;
  #   flavor = "mocha";
  #   accent = "mauve";
  #   enableRounded = true;
  #   apply = false;
  # };
}
