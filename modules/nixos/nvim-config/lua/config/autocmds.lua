-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
--
-- Add any additional autocmds here
-- with `vim.api.nvim_create_autocmd`
--
-- Or remove existing autocmds by their group name (which is prefixed with `lazyvim_` for the defaults)
-- e.g. vim.api.nvim_del_augroup_by_name("lazyvim_wrap_spell")

-- iTerm2's inline browser changes the terminal size when it opens or closes.
-- LazyVim normally equalizes every split on VimResized, which destroys the
-- width chosen by leetcode.nvim for its description and editor panes.
pcall(vim.api.nvim_del_augroup_by_name, "lazyvim_resize_splits")

local resize_group = vim.api.nvim_create_augroup("user_resize_splits", { clear = true })

local function is_leetcode_tab(tabpage)
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(tabpage)) do
    local buf = vim.api.nvim_win_get_buf(win)
    if vim.bo[buf].filetype == "leetcode.nvim" then
      return true
    end
  end
  return false
end

vim.api.nvim_create_autocmd("VimResized", {
  group = resize_group,
  callback = function()
    for _, tabpage in ipairs(vim.api.nvim_list_tabpages()) do
      if not is_leetcode_tab(tabpage) then
        local wins = vim.api.nvim_tabpage_list_wins(tabpage)
        if wins[1] then
          vim.api.nvim_win_call(wins[1], function()
            vim.cmd("wincmd =")
          end)
        end
      end
    end
  end,
  desc = "Equalize normal splits without disturbing LeetCode layouts",
})
