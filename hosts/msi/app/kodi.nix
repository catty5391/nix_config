{pkgs, ...}: {
  environment.systemPackages = [
    # Use native Wayland on Niri; the X11 build stalls during video playback.
    pkgs.kodi-wayland
  ];
}
