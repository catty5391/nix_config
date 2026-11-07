_: {
  programs.kitty = {
    enable = true;
    font = {
      name = "JetBrainsMono Nerd Font";
      size = 18;
    };
    settings = {
      # Allow remote applications (for example Neovim over SSH) to read the
      # local clipboard through OSC 52 without prompting each time.
      clipboard_control = "write-clipboard write-primary read-clipboard read-primary";
    };
    extraConfig = ''
      # NyxNiri presentation; colors are managed by catppuccin.kitty below.
      window_padding_width 5
      cursor_trail 1
      cursor_shape block
      bold_font auto
      italic_font auto
      bold_italic_font auto
      background_opacity 1.0
      background_blur 0
      hide_window_decorations yes
      confirm_os_window_close 0
      remember_window_size no
      force_ltr_rendering yes
      disable_ligature

      map ctrl+c copy_or_interrupt
      map ctrl+v paste_from_clipboard
      map ctrl+backspace send_text all \x17
      map ctrl+delete send_text all \x1bd
      map ctrl+a pipe @text clipboard sh -c "wl-copy 2>/dev/null"
      map ctrl+equal change_font_size all +1.0
      map ctrl+minus change_font_size all -1.0
      map ctrl+0 change_font_size all 0
      mouse_map ctrl+scroll_up change_font_size all +1.0
      mouse_map ctrl+scroll_down change_font_size all -1.0
    '';
  };

  catppuccin.kitty = {
    enable = true;
    flavor = "mocha";
  };
}
