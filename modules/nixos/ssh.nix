{...}: {
  services.openssh = {
    enable = true;
    ports = [60003];
    openFirewall = true;
    settings = {
      PermitRootLogin = "yes";
      PubkeyAuthentication = "yes";
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
    };
  };
  programs.ssh.extraConfig = ''
    Host github.com
      HostName github.com
      User git
      IdentityFile ~/.ssh/github
      IdentitiesOnly yes
      ServerAliveInterval 60
      ServerAliveCountMax 3

    Host nas
      HostName 192.168.5.155
      User root
      Port 60003
      IdentityFile ~/.ssh/nas
      IdentitiesOnly yes
      ServerAliveCountMax 3
      ServerAliveInterval 60
  '';
}
