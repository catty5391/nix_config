{
  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;

    settings."github.com" = {
      HostName = "github.com";
      User = "git";
      IdentityFile = "~/.ssh/github";
      IdentitiesOnly = true;
      ServerAliveInterval = 60;
      ServerAliveCountMax = 3;
    };
    settings."nas" = {
      HostName = "192.168.5.155";
      User = "root";
      Port = "60003";
      IdentityFile = "~/.ssh/nas";
      IdentitiesOnly = true;
      ServerAliveCountMax = 3;
      ServerAliveInterval = 60;
    };
  };
}
