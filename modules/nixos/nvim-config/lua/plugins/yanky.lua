return {
  {
    "gbprod/yanky.nvim",
    event = "VeryLazy",
    opts = {
      ring = {
        history_length = 100,
        storage = "shada",
        sync_with_numbered_registers = true,
      },
      system_clipboard = {
        sync_with_ring = true,
        clipboard_register = "+",
      },
      highlight = {
        on_yank = true,
        on_put = true,
        timer = 200,
      },
      preserve_cursor_position = {
        enabled = true,
      },
    },
    keys = {
      {
        "<leader>ty",
        function()
          require("lazy").load({ plugins = { "telescope.nvim" } })
          local telescope = require("telescope")
          telescope.load_extension("yank_history")
          telescope.extensions.yank_history.yank_history()
        end,
        mode = { "n", "x" },
        desc = "Telescope: yank history",
      },
      { "y", "<Plug>(YankyYank)", mode = { "n", "x" }, desc = "Yank text" },
      { "p", "<Plug>(YankyPutAfter)", mode = { "n", "x" }, desc = "Put text after cursor" },
      { "P", "<Plug>(YankyPutBefore)", mode = { "n", "x" }, desc = "Put text before cursor" },
      { "gp", "<Plug>(YankyGPutAfter)", mode = { "n", "x" }, desc = "Put text and move after it" },
      { "gP", "<Plug>(YankyGPutBefore)", mode = { "n", "x" }, desc = "Put text before and move after it" },
      { "[y", "<Plug>(YankyCycleForward)", desc = "Previous yank history entry" },
      { "]y", "<Plug>(YankyCycleBackward)", desc = "Next yank history entry" },
      { "]p", "<Plug>(YankyPutIndentAfterLinewise)", desc = "Put indented after cursor" },
      { "[p", "<Plug>(YankyPutIndentBeforeLinewise)", desc = "Put indented before cursor" },
    },
  },
}
