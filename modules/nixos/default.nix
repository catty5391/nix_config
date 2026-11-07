{...}: {
  imports = [
    ./base.nix
    ./desktop.nix
    ./ssh.nix
    ./virtualization.nix
    ./zsh.nix
    ./tailscale.nix
    ./proxy.nix
    ./nixvim.nix
    ./llm.nix
  ];
}
