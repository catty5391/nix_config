{
  imports = [
    ./hardware-configuration.nix
    ./hardware.nix
    ./networking.nix
    ./storage.nix
    ./telegram-openlist-sync.nix
    ../../modules/nixos
  ];

  networking.hostName = "nas";
  services.telegram-openlist-sync.enable = true;

  # Keep this at the release used for the first installation.
  system.stateVersion = "26.05";
}
