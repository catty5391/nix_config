{
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
