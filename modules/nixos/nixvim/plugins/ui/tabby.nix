{pkgs, ...}: {
  opts.showtabline = 2;

  extraPlugins = with pkgs.vimPlugins; [
    nvim-web-devicons
    tabby-nvim
  ];

  extraFiles."lua/knight/tabby.lua".source = ./tabby.lua;
  extraConfigLua = ''
    require("knight.tabby").setup()
  '';
}
