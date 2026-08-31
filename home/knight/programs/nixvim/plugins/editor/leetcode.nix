{pkgs, ...}: {
  plugins.leetcode = {
    enable = true;
    settings = {
      lang = "java";
      cn = {
        enabled = true;
        translator = true;
        translate_problems = true;
      };
      picker.provider = "fzf-lua";
      plugins.non_standalone = true;
    };
  };

  extraPlugins = with pkgs.vimPlugins; [
    fzf-lua
    nui-nvim
    plenary-nvim
  ];

  keymaps = [
    {
      mode = "n";
      key = "<leader>ol";
      action = "<cmd>Leet<cr>";
      options.desc = "LeetCode";
    }
  ];
}
