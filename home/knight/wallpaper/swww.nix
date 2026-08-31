_: {
  # Keep the existing image library; Noctalia/mpvpaper now owns rendering.
  home.file.".config/wallpaper" = {
    source = ./image;
    recursive = true;
  };
}
