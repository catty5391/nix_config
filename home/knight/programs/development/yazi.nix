{pkgs, ...}: {
  programs.yazi = {
    enable = true;

    plugins.git = {
      package = pkgs.yaziPlugins.git;
      setup = true;
    };
  };
}
