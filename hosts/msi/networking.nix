{lib, ...}: {
  networking.networkmanager = {
    enable = true;
    settings.connection."ipv6.ip6-privacy" = 2;
  };
  networking.hostName = "MSI";
}
