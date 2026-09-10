{lib, ...}: {
  imports = [
    ./core
    ./plugins
  ];

  viAlias = true;
  vimAlias = true;
  withNodeJs = true;
  withPython3 = true;

  # Match the previous LazyVim workflow: Tabby owns the top bar and Yazi is
  # the file browser, so competing buffer/tree UIs stay disabled.
  plugins.bufferline.enable = lib.mkForce false;
  plugins.neo-tree.enable = lib.mkForce false;
  plugins.mini-files.enable = lib.mkForce false;
}
