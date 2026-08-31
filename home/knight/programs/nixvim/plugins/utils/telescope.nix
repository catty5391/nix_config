{lib, ...}: {
  keymaps = [
    {
      mode = "n";
      key = "<leader>tf";
      action = lib.nixvim.mkRaw ''
        function()
          require("telescope.builtin").find_files({ hidden = true })
        end
      '';
      options.desc = "Telescope: find files";
    }
    {
      mode = "n";
      key = "<leader>tg";
      action = lib.nixvim.mkRaw ''require("telescope.builtin").live_grep'';
      options.desc = "Telescope: grep project";
    }
    {
      mode = "n";
      key = "<leader>tb";
      action = lib.nixvim.mkRaw ''
        function()
          require("telescope.builtin").buffers({
            sort_mru = true,
            ignore_current_buffer = true,
          })
        end
      '';
      options.desc = "Telescope: buffers";
    }
    {
      mode = "n";
      key = "<leader>ts";
      action = lib.nixvim.mkRaw ''require("telescope.builtin").current_buffer_fuzzy_find'';
      options.desc = "Telescope: search current buffer";
    }
    {
      mode = "n";
      key = "<leader>tr";
      action = lib.nixvim.mkRaw ''require("telescope.builtin").oldfiles'';
      options.desc = "Telescope: recent files";
    }
    {
      mode = "n";
      key = "<leader>td";
      action = lib.nixvim.mkRaw ''require("telescope.builtin").diagnostics'';
      options.desc = "Telescope: diagnostics";
    }
    {
      mode = "n";
      key = "<leader>th";
      action = lib.nixvim.mkRaw ''require("telescope.builtin").help_tags'';
      options.desc = "Telescope: help";
    }
    {
      mode = "n";
      key = "<leader>tt";
      action = lib.nixvim.mkRaw ''require("telescope.builtin").builtin'';
      options.desc = "Telescope: all pickers";
    }
    {
      mode = ["n" "x"];
      key = "<leader>ty";
      action = lib.nixvim.mkRaw ''
        function()
          require("telescope").extensions.yank_history.yank_history()
        end
      '';
      options.desc = "Telescope: yank history";
    }
  ];
}
