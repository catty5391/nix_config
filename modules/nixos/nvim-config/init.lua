-- bootstrap lazy.nvim, LazyVim and your plugins
require("config.lazy")
vim.keymap.set("i", "jj", "<ESC>", { noremap = true, silent = true, desc = "Exit Insert with jk" })

vim.opt.timeout = true
vim.opt.timeoutlen = 300
-- 同步系统剪切板
vim.g.clipboard = {
  name = "OSC 52",
  copy = {
    ["+"] = require("vim.ui.clipboard.osc52").copy("+"),
    ["*"] = require("vim.ui.clipboard.osc52").copy("*"),
  },
  paste = {
    ["+"] = require("vim.ui.clipboard.osc52").paste("+"),
    ["*"] = require("vim.ui.clipboard.osc52").paste("*"),
  },
}

vim.opt.clipboard = "unnamedplus"
vim.api.nvim_set_hl(0, "WinSeparator", { fg = "#ff0000", bold = true })
