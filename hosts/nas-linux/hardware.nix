{pkgs, ...}: {
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  hardware = {
    bluetooth.enable = true;
    enableAllFirmware = true;
    i2c.enable = true;
    cpu.intel.updateMicrocode = true;
  };

  hardware.graphics = {
    enable = true;
    enable32Bit = true;
    extraPackages = [pkgs.intel-media-driver];
    extraPackages32 = [pkgs.pkgsi686Linux.intel-media-driver];
  };
}
