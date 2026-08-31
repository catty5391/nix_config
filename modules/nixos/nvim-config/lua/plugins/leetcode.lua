return {
  "kawre/leetcode.nvim",
  cmd = "Leet",
  build = ":TSUpdate html",
  dependencies = {
    "nvim-lua/plenary.nvim",
    "MunifTanjim/nui.nvim",
    "nvim-treesitter/nvim-treesitter",
    "ibhagwan/fzf-lua",
  },
  opts = {
    lang = "java",
    cn = {
      enabled = true,
      translator = true,
      translate_problems = true,
    },
    picker = {
      provider = "fzf-lua",
    },
    plugins = {
      non_standalone = true,
    },
  },
  keys = {
    {
      "<leader>ol",
      "<cmd>Leet<cr>",
      desc = "LeetCode",
    },
  },
}
