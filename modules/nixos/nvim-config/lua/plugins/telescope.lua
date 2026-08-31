return {
  {
    "nvim-telescope/telescope.nvim",
    tag = "0.1.8",
    cmd = "Telescope",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "nvim-tree/nvim-web-devicons",
    },
    keys = {
      {
        "<leader>tf",
        function()
          require("telescope.builtin").find_files({ hidden = true })
        end,
        desc = "Telescope: find files",
      },
      {
        "<leader>tg",
        function()
          require("telescope.builtin").live_grep()
        end,
        desc = "Telescope: grep project",
      },
      {
        "<leader>tb",
        function()
          require("telescope.builtin").buffers({ sort_mru = true, ignore_current_buffer = true })
        end,
        desc = "Telescope: buffers",
      },
      {
        "<leader>ts",
        function()
          require("telescope.builtin").current_buffer_fuzzy_find()
        end,
        desc = "Telescope: search current buffer",
      },
      {
        "<leader>tr",
        function()
          require("telescope.builtin").oldfiles()
        end,
        desc = "Telescope: recent files",
      },
      {
        "<leader>td",
        function()
          require("telescope.builtin").diagnostics()
        end,
        desc = "Telescope: diagnostics",
      },
      {
        "<leader>th",
        function()
          require("telescope.builtin").help_tags()
        end,
        desc = "Telescope: help",
      },
      {
        "<leader>tt",
        function()
          require("telescope.builtin").builtin()
        end,
        desc = "Telescope: all pickers",
      },
    },
    opts = function()
      local actions = require("telescope.actions")

      return {
        defaults = {
          prompt_prefix = "   ",
          selection_caret = "󰜴 ",
          layout_strategy = "horizontal",
          layout_config = {
            horizontal = {
              preview_width = 0.55,
            },
            width = 0.90,
            height = 0.85,
            prompt_position = "top",
          },
          sorting_strategy = "ascending",
          path_display = { "smart" },
          mappings = {
            i = {
              ["<C-j>"] = actions.move_selection_next,
              ["<C-k>"] = actions.move_selection_previous,
              ["<Esc>"] = actions.close,
            },
          },
        },
      }
    end,
  },
}
