{config, lib, pkgs, ...}: let
  cfg = config.services.telegram-openlist-sync;
in {
  options.services.telegram-openlist-sync = {
    enable = lib.mkEnableOption "Telegram OpenList scan bot";
    environmentFile = lib.mkOption {
      type = lib.types.str;
      default = "/etc/telegram-openlist-sync.env";
      description = "Absolute runtime environment file; keep credentials out of the Nix store.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [{
      assertion = lib.hasPrefix "/" cfg.environmentFile && !(lib.hasPrefix "/nix/store/" cfg.environmentFile);
      message = "telegram-openlist-sync.environmentFile must be an absolute path outside the Nix store.";
    }];
    systemd.services.telegram-openlist-sync = {
      description = "Telegram OpenList scan bot";
      wantedBy = ["multi-user.target"];
      wants = ["network-online.target"];
      after = ["network-online.target"];
      environment = {
        PYTHONUNBUFFERED = "1";
        PYTHONDONTWRITEBYTECODE = "1";
        SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
      };
      serviceConfig = {
        ExecStart = "${pkgs.python3}/bin/python3 ${./telegram-openlist-sync}/bot.py";
        EnvironmentFile = cfg.environmentFile;
        DynamicUser = true;
        StateDirectory = "telegram-openlist-sync";
        StateDirectoryMode = "0700";
        Restart = "on-failure";
        RestartSec = 10;
        TimeoutStopSec = 45;
        UMask = "0077";
        NoNewPrivileges = true;
        PrivateTmp = true;
        PrivateDevices = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictSUIDSGID = true;
        RestrictAddressFamilies = ["AF_UNIX" "AF_INET" "AF_INET6"];
        CapabilityBoundingSet = "";
      };
    };
  };
}
