{...}: {
  imports = [
    ./base.nix
    ./desktop.nix
    ./ssh.nix
    ./virtualization.nix
    ./zsh.nix
    ./java.nix
    ./tailscale.nix
    ./proxy.nix
    ./seu-autologin.nix
    ./nixvim.nix
  ];
}
