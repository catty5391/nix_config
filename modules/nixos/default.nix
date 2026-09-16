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
    ./nixvim.nix
    ./llm.nix
  ];
}
