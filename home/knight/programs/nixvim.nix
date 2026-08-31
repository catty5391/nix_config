{
  config,
  inputs,
  lib,
  pkgs,
  ...
}: let
  system = pkgs.stdenv.hostPlatform.system;
  baseNixvim = inputs.CookNixvim.packages.${system}.default;
  nixvim = baseNixvim.extend (import ./nixvim);
in {
  # NixVim is scoped to knight; root keeps the system Neovim as a recovery
  # editor.
  home.packages = [nixvim];

  home.sessionVariables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
  };

  # CookNixvim stores the selected theme in stdpath("data")/theme. Seed a
  # familiar default once, while keeping later changes made with <leader>T.
  home.activation.seedNixvimTheme = lib.hm.dag.entryAfter ["writeBoundary"] ''
    theme_dir="${config.xdg.dataHome}/nvim"
    theme_file="$theme_dir/theme"
    mkdir -p "$theme_dir"
    if [ ! -s "$theme_file" ]; then
      printf '%s\n' 'tokyonight-moon:dark' > "$theme_file"
    fi
  '';
}
