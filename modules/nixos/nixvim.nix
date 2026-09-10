{
  inputs,
  pkgs,
  ...
}: let
  system = pkgs.stdenv.hostPlatform.system;
  baseNixvim = inputs.CookNixvim.packages.${system}.default;
  nixvim = baseNixvim.extend (import ./nixvim);
in {
  # The package embeds the shared configuration for every user, including root.
  environment.systemPackages = [nixvim] ++ (with pkgs; [
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
  ]);

  environment.sessionVariables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
  };

  environment.pathsToLink = ["/share/nvim"];
}
