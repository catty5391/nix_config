{lib, pkgs, ...}: let
  niriGdmSession = pkgs.runCommand "niri-gdm-session" {
    passthru.providedSessions = ["niri"];
  } ''
    mkdir -p $out/share/wayland-sessions
    substitute ${pkgs.niri}/share/wayland-sessions/niri.desktop \
      $out/share/wayland-sessions/niri.desktop \
      --replace-fail "Exec=niri-session" "Exec=${pkgs.niri}/bin/niri-session"
  '';
in {
  fonts = {
    enableDefaultPackages = true;
    packages = with pkgs; [
      noto-fonts
      noto-fonts-cjk-sans
      noto-fonts-color-emoji
      dejavu_fonts
      nerd-fonts.fira-code
      nerd-fonts.jetbrains-mono
    ];
    fontconfig = {
      enable = true;
      defaultFonts = {
        serif = ["Noto Sans" "Noto Sans CJK SC"];
        sansSerif = ["Noto Serif" "Noto Serif CJK SC"];
        monospace = ["Fira Code"];
      };
    };
  };

  programs.niri.enable = true;
  programs.xwayland.enable = true;

  services.displayManager.gdm.enable = true;
  services.displayManager.sessionPackages = lib.mkForce [niriGdmSession];
  services.displayManager.defaultSession = "niri";
  services.xserver.enable = true;

  services.gnome.gnome-keyring.enable = true;
  security.pam.services.gdm.enableGnomeKeyring = true;

  services.blueman.enable = true;
  services.power-profiles-daemon.enable = true;
  services.upower.enable = true;
}
