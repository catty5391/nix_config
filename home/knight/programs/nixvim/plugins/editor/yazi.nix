{
  globals.loaded_netrwPlugin = 1;

  plugins.yazi = {
    enable = true;
    settings = {
      open_for_directories = false;
      keymaps.show_help = "<f1>";
    };
  };

  keymaps = [
    {
      mode = ["n" "v"];
      key = "<leader>fy";
      action = "<cmd>Yazi<cr>";
      options.desc = "Open Yazi at current file";
    }
    {
      mode = "n";
      key = "<leader>cw";
      action = "<cmd>Yazi cwd<cr>";
      options.desc = "Open Yazi in working directory";
    }
    {
      mode = "n";
      key = "<leader>yr";
      action = "<cmd>Yazi toggle<cr>";
      options.desc = "Resume last Yazi session";
    }
  ];
}
