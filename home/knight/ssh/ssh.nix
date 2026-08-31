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
  };
}
