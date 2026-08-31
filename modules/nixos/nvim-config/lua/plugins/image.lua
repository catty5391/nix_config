return {
  "3rd/image.nvim",
  enabled = false,
  build = false,
  opts = {
    backend = "ueberzug",
    processor = "magick_cli",
    integrations = {
      markdown = { enabled = false },
      asciidoc = { enabled = false },
      neorg = { enabled = false },
      rst = { enabled = false },
      typst = { enabled = false },
      html = { enabled = false },
      css = { enabled = false },
    },
    max_width = 80,
    max_height = 24,
    max_height_window_percentage = 50,
    window_overlap_clear_enabled = true,
    window_overlap_clear_ft_ignore = { "cmp_menu", "cmp_docs", "snacks_notif" },
  },
}
