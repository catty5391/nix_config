{osConfig, ...}: {
  imports = [
    ./kitty.nix
    ./alacritty.nix
    ./ghostty.nix
    ./termius.nix
  ];

  # Manage the user config with the same settings as the system prompt.
  # Shell initialization is already provided by the NixOS Starship module.
  programs.starship = {
    inherit (osConfig.programs.starship) enable package presets settings;
    enableBashIntegration = false;
    enableZshIntegration = false;
    enableFishIntegration = false;
    enableIonIntegration = false;
    enableNushellIntegration = false;
  };
}
