{
  imports = [
    ./hardware-configuration.nix
    ./hardware.nix
    ./networking.nix
    ../../modules/nixos
  ];
  boot.loader.systemd-boot.enable = false;
  boot.loader.grub = {
    enable = true;
    efiSupport = true;
    efiInstallAsRemovable = true;
    device = "nodev";
    useOSProber = true;
  };

  boot.loader.efi = {
    canTouchEfiVariables = false;
    efiSysMountPoint = "/boot";
  };

  # Keep this at the release used for the first installation.
  system.stateVersion = "26.05";
}
