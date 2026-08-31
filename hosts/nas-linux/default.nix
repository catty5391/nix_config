{
  imports = [
    ./hardware-configuration.nix
    ./hardware.nix
    ./networking.nix
    ./storage.nix
    ../../modules/nixos
  ];

  networking.hostName = "nas";

  # Keep this at the release used for the first installation.
  system.stateVersion = "26.05";
}
