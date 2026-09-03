{pkgs, ...}: {
  programs.yazi = {
    enable = true;

    plugins.git = {
      package = pkgs.yaziPlugins.git;
      setup = true;
    };
    settings = {
      plugin = {
        prepend_fetchers = [
            {
            url = "*";
            run = "git";
            group = "git";
            }
            {
            url = "*/";
            run = "git";
            group = "git";
            }
        ];
      };
    };
  };
}
