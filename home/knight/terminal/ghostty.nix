_: {
  programs.ghostty = {
    enable = true;
    systemd.enable = false;
    installBatSyntax = false;
    settings.font-family = "JetBrainsMono Nerd Font";
  };

  catppuccin.ghostty = {
    enable = true;
    flavor = "mocha";
  };
}
