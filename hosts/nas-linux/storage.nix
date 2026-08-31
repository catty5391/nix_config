{ ... }:

{
  fileSystems."/volume1" = {
    device = "/dev/disk/by-uuid/6ef4716a-3072-4120-a145-15b0dd3fed1a";
    fsType = "btrfs";
    options = [
      "noatime"
      "compress=zstd:3"
      "nofail"
      "x-systemd.device-timeout=30s"
    ];
  };

  fileSystems."/volume2" = {
    device = "/dev/disk/by-uuid/00444fe7-2bc1-4460-a017-8ef051bac402";
    fsType = "btrfs";
    options = [
      "noatime"
      "compress=zstd:3"
      "nofail"
      "x-systemd.device-timeout=30s"
    ];
  };
}
