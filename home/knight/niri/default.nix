{
  config,
  inputs,
  lib,
  pkgs,
  ...
}: let
  upstream = inputs.nyxniri;

  pythonEnv = pkgs.python3.withPackages (pythonPackages:
    with pythonPackages; [
      pycairo
      pygobject3
    ]);

  giTypelibPath = lib.makeSearchPath "lib/girepository-1.0" [
    (lib.getLib pkgs.at-spi2-core)
    pkgs.gdk-pixbuf
    pkgs.gobject-introspection
    pkgs.gtk3
    pkgs.gtk-layer-shell
    (lib.getLib pkgs.harfbuzz)
    (lib.getLib pkgs.pango)
  ];

  wallpaperPicker = pkgs.writeShellScriptBin "nyxniri-wallpaper-picker" ''
    export GI_TYPELIB_PATH="${giTypelibPath}:$GI_TYPELIB_PATH"
    exec ${pythonEnv}/bin/python ${upstream}/configs/niri/scripts/wallpaper-picker.py "$@"
  '';

  orbitLauncher = pkgs.writeShellScriptBin "nyxniri-orbit-launcher" ''
    export GI_TYPELIB_PATH="${giTypelibPath}:$GI_TYPELIB_PATH"
    exec ${pythonEnv}/bin/python ${orbitScripts}/orbit-launcher.py "$@"
  '';

  # NyxNiri assumes an FHS system and invokes /bin/bash after an Orbit item is
  # selected. NixOS intentionally has no /bin/bash, so patch the immutable
  # upstream scripts to use the Bash package from this system closure.
  orbitScripts = pkgs.runCommand "nyxniri-orbit-scripts" {} ''
    cp -R ${upstream}/configs/niri/scripts "$out"
    chmod -R u+w "$out"
    substituteInPlace "$out/orbit/window.py" \
      --replace-fail '/bin/bash' '${pkgs.bash}/bin/bash'
  '';

  eyeCare = pkgs.writeShellScriptBin "nyxniri-eyecare" ''
    exec ${pkgs.bash}/bin/bash ${upstream}/configs/niri/scripts/toggle-eyecare.sh "$@"
  '';

  scratchToggle = pkgs.writeShellScriptBin "nyxniri-scratch-toggle" ''
    exec ${pkgs.bash}/bin/bash ${upstream}/configs/niri/scripts/niri-scratch-toggle.sh "$@"
  '';

  # Retain the upstream binding layout, but run the GTK launchers through
  # wrappers that provide their GI dependencies on NixOS.
  bindsText = builtins.replaceStrings
    [
      ''spawn "~/.config/niri/scripts/wallpaper-picker.py";''
      ''spawn "~/.config/niri/scripts/orbit-launcher.py";''
      ''spawn "~/.config/niri/scripts/toggle-eyecare.sh";''
      ''spawn "~/.config/niri/scripts/niri-scratch-toggle.sh" "kitty";''
    ]
    [
      ''spawn "nyxniri-wallpaper-picker";''
      ''spawn "nyxniri-orbit-launcher";''
      ''spawn "nyxniri-eyecare";''
      ''spawn "nyxniri-scratch-toggle" "kitty";''
    ]
    (builtins.readFile "${upstream}/configs/niri/binds.kdl");

  layoutText = builtins.replaceStrings
    [
      "        off\n        width 0"
    ]
    [
      "        on\n        width 2"
    ]
    (builtins.readFile "${upstream}/configs/niri/layout.kdl");
in {
  programs.fuzzel.enable = true;
  catppuccin.fuzzel = {
    enable = true;
    accent = "mauve";
    flavor = "mocha";
  };

  home.packages = with pkgs; [
    ddcutil
    nautilus
    tmux
    wlsunset
    xdg-user-dirs
    eyeCare
    orbitLauncher
    scratchToggle
    wallpaperPicker
  ];

  xdg.configFile = {
    "niri/config.kdl".source = ./config.kdl;
    "niri/monitor.kdl".source = ./monitor.kdl;
    "niri/input__custom__.kdl".source = ./input__custom__.kdl;
    "niri/__custom__.kdl".source = ./__custom__.kdl;
    "niri/orbit-items__custom__.toml".source = ./orbit-items__custom__.toml;

    "niri/layout.kdl".text = layoutText;
    "niri/animations.kdl".source = "${upstream}/configs/niri/animations.kdl";
    "niri/rules.kdl".source = "${upstream}/configs/niri/rules.kdl";
    "niri/binds.kdl".text = bindsText;
    "niri/effects_normal.kdl".source = "${upstream}/configs/niri/effects_normal.kdl";
    "niri/effects_eyecare.kdl".source = "${upstream}/configs/niri/effects_eyecare.kdl";
    "niri/effects.kdl" = {
      source = "${upstream}/configs/niri/effects_normal.kdl";
      force = true;
    };
    "niri/scripts" = {
      source = orbitScripts;
      recursive = true;
    };
  };

  home.activation.ensureNyxNiriDirectories = lib.hm.dag.entryAfter ["writeBoundary"] ''
    mkdir -p \
      "${config.home.homeDirectory}/Pictures/Screenshots" \
      "${config.home.homeDirectory}/.config/wallpaper/video"
  '';
}
