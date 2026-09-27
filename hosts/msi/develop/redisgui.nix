{pkgs, ...}: {
  environment.systemPackages = [
    pkgs.redisinsight
  ];
}
