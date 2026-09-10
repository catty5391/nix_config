{
  # Seed each user's theme before CookNixvim loads it, preserving saved choices.
  extraConfigLuaPre = ''
    do
      local data_dir = vim.fn.stdpath("data")
      local theme_file = data_dir .. "/theme"
      local file = io.open(theme_file, "r")
      local saved_theme = file and file:read("*a") or ""
      if file then
        file:close()
      end

      -- CookNixvim uses the saved background verbatim; remove legacy newlines.
      local theme = saved_theme:gsub("%s+$", "")
      if theme == "" then
        theme = "tokyonight-moon:dark"
      end
      if theme ~= saved_theme then
        pcall(function()
          vim.fn.mkdir(data_dir, "p")
          vim.fn.writefile({ theme }, theme_file, "b")
        end)
      end
    end
  '';

  autoCmd = [
    {
      event = "VimEnter";
      once = true;
      desc = "Use TokyoNight when no saved CookNixvim theme exists";
      callback.__raw = ''
        function()
          vim.schedule(function()
            if vim.g.colors_name == nil or vim.g.colors_name == "default" then
              pcall(vim.cmd.colorscheme, "tokyonight-moon")
            end
          end)
        end
      '';
    }
  ];
}
