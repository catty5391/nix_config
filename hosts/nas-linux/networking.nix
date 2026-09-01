{lib, ...}: {
  networking.networkmanager = {
    enable = true;
    settings.connection."ipv6.ip6-privacy" = 0;
  };

  networking.firewall = {
    enable = true;
    allowedTCPPorts = [
      30001
      9876
      9090
      8080
      45123
      5244
      8096
      7789
    ];
    allowedUDPPorts = [45123];
  };

  boot.kernel.sysctl = {
    "net.ipv6.conf.all.use_tempaddr" = lib.mkForce 0;
    "net.ipv6.conf.default.use_tempaddr" = lib.mkForce 0;
  };
}
