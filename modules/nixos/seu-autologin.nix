{
  pkgs,
  inputs,
  ...
}: let
  seu-autologin = pkgs.writeShellApplication {
    name = "seu-autologin";

    runtimeInputs = with pkgs; [
      curl
      jq
      gnused
      networkmanager
      iputils
    ];

    text = builtins.readFile "${inputs.seu-autologin}/seu-autologin.sh";
  };
in {
  systemd.services.seu-autologin = {
    description = "SEU WLAN AUTO LOGIN";

    wantedBy = ["multi-user.target"];

    after = [
      "NetworkManager.service"
      "network-online.target"
    ];

    wants = [
      "network-online.target"
    ];

    serviceConfig = {
      Type = "simple";

      ExecStart = "${seu-autologin}/bin/seu-autologin";
      EnvironmentFile = "/etc/seu-autologin.env";

      Restart = "always";
      RestartSec = 5;

      User = "root";
    };
  };
}
