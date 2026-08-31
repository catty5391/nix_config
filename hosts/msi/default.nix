{
  imports = [
    ./hardware-configuration.nix
    ./hardware.nix
    ./networking.nix
    ../../modules/nixos
  ];
  boot.loader.systemd-boot.enable = true;
  
  boot.loader.efi = {
    canTouchEfiVariables = true;
    efiSysMountPoint = "/boot";
  };

  # Keep this at the release used for the first installation.
  system.stateVersion = "26.05";
}
