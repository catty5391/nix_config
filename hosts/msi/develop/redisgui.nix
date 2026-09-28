{pkgs-unstable, ...}: {
  environment.systemPackages = [
    (pkgs-unstable.redisinsight.override {
      # The pinned RedisInsight package still defaults to EOL Electron 41.
      electron_41 = pkgs-unstable.electron_43;
    })
  ];
}
