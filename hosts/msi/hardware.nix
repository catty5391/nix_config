{
  config,
  pkgs,
  ...
}: {
  # Enable NVIDIA's VA-API/NVDEC path in Google Chrome. Without these flags,
  # video pages fall back to CPU decoding and repeatedly upload frames to the
  # GPU, which can make Chrome's renderer and GPU process spike together.
  nixpkgs.overlays = [
    (_final: prev: {
      google-chrome = prev.google-chrome.override {
        commandLineArgs = "--ozone-platform=wayland --enable-features=WaylandWindowDecorations,AcceleratedVideoDecodeLinuxGL,VaapiOnNvidiaGPUs --enable-wayland-ime=true --ignore-gpu-blocklist --use-gl=angle --use-angle=gl";
      };
    })
  ];

  environment.sessionVariables = {
    LIBVA_DRIVER_NAME = "nvidia";
    NVD_BACKEND = "direct";
  };

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

  services.xserver.videoDrivers = ["nvidia"];

  hardware.nvidia = {
    # Required for Wayland compositors such as Niri.
    modesetting.enable = true;

    # RTX 50-series GPUs use NVIDIA's supported open kernel modules.
    open = true;

    nvidiaSettings = true;
    package = config.boot.kernelPackages.nvidiaPackages.stable;
  };

  # Prevent NVIDIA's Wayland buffer pool from retaining close to 1 GiB of
  # VRAM in Niri. This profile is recommended by Niri upstream.
  environment.etc."nvidia/nvidia-application-profiles-rc.d/50-limit-free-buffer-pool-in-wayland-compositors.json".text =
    builtins.toJSON {
      rules = [
        {
          pattern = {
            feature = "procname";
            matches = "niri";
          };
          profile = "Limit Free Buffer Pool On Wayland Compositors";
        }
      ];
      profiles = [
        {
          name = "Limit Free Buffer Pool On Wayland Compositors";
          settings = [
            {
              key = "GLVidHeapReuseRatio";
              value = 0;
            }
          ];
        }
      ];
    };
}
