{ pkgs, ... }:

{
  # Neovim itself is managed by NixOS.  Plugins remain pinned by the
  # lazy-lock.json copied from the Mac configuration.
  programs.neovim = {
    enable = true;
    defaultEditor = true;
    viAlias = true;
    vimAlias = true;
    withNodeJs = true;
    withPython3 = true;
  };

  # External commands used by LazyVim, Telescope, Treesitter, Mason, Yazi,
  # LeetCode (Java), and the configured language extras.
  environment.systemPackages = with pkgs; [
    git
    curl
    unzip
    gnutar
    gzip

    gcc
    tree-sitter
    gnumake
    pkg-config

    ripgrep
    fd
    fzf
    yazi

    nodejs
    python3
    clang-tools
    lua-language-server

    stylua
  ];

  # Copy the Mac ~/.config/nvim directory to ./nvim-config next to this file.
  # NixOS publishes that immutable configuration at /etc/nvim-config.
  environment.etc."nvim-config".source = ./nvim-config;

  # This server is currently administered as root, so expose the declarative
  # configuration at the path Neovim normally reads for root.
  systemd.tmpfiles.rules = [
    "d /root/.config 0700 root root - -"
    "L+ /root/.config/nvim - - - - /etc/nvim-config"
  ];
}
