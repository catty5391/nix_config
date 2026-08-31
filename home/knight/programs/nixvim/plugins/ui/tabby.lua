local M = {}

function M.setup()
  require("tabby").setup({
    line = function(line)
      local theme = {
        fill = { fg = "#565f89", bg = "#1e2030" },
        head = { fg = "#1e2030", bg = "#ff9e64", style = "bold" },
        tab = { fg = "#7f849c", bg = "#292e42" },
        current_tab = { fg = "#c8d3f5", bg = "#3b4261", style = "bold" },
        win = { fg = "#7f849c", bg = "#222436" },
        current_win = { fg = "#c8d3f5", bg = "#292e42", style = "bold" },
      }

      local project = vim.fn.fnamemodify(vim.fn.getcwd(), ":t")
      if project == "" then
        project = "nvim"
      end

      return {
        {
          { " " .. project .. " ", hl = theme.head },
          line.sep("", theme.head, theme.fill),
        },
        line.tabs().foreach(function(tab)
          local hl = tab.is_current() and theme.current_tab or theme.tab
          return {
            line.sep("", hl, theme.fill),
            tab.is_current() and "▣" or "□",
            tab.number(),
            line.sep("", hl, theme.fill),
            hl = hl,
            margin = " ",
          }
        end),
        line.spacer(),
        line.wins_in_tab(line.api.get_current_tab()).foreach(function(win)
          local hl = win.is_current() and theme.current_win or theme.win
          return {
            line.sep("", hl, theme.fill),
            win.is_current() and "● " or "○ ",
            win.file_icon(),
            " ",
            win.buf_name(),
            win.buf().is_changed() and " ●" or "",
            line.sep("", hl, theme.fill),
            hl = hl,
            margin = " ",
          }
        end),
        { " 󰈔 ", hl = theme.fill },
        hl = theme.fill,
      }
    end,
    option = {
      buf_name = { mode = "unique" },
    },
  })
end

return M
