{pkgs, ...}: {
  environment.systemPackages = [
    (pkgs.tsukimi.overrideAttrs (old: {
      patches = (old.patches or []) ++ [./tsukimi-strm.patch];

      # libmpv/FFmpeg loads libcuda dynamically from the active NVIDIA driver.
      preFixup = (old.preFixup or "") + ''
        gappsWrapperArgs+=(--prefix LD_LIBRARY_PATH : /run/opengl-driver/lib)
      '';
    }))
  ];
}
