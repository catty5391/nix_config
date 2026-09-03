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
            id = "git";
            name = "*";
            run = "git";
          }
          {
            id = "git";
            name = "*/";
            run = "git";
          }
        ];
      };
    };
  };
}
