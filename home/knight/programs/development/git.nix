{
  programs.git = {

    enable = true;

    settings = {
      user = {
        name = "knight";
        email = "2579671619@qq.com";
      };

      init.defaultBranch = "main";
      core.editor = "nvim";
    };
  };
}

