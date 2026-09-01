{...}: {
  imports = [
    ./base.nix
    ./desktop.nix
    ./ssh.nix
    ./nvim.nix
    ./virtualization.nix
    ./zsh.nix
    ./java.nix
    ./tailscale.nix
    ./proxy.nix
  ];
}
