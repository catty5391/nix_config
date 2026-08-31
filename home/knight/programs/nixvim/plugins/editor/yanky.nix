{
  plugins.yanky = {
    enable = true;
    enableTelescope = true;
    settings = {
      ring = {
        history_length = 100;
        storage = "shada";
        sync_with_numbered_registers = true;
      };
      system_clipboard = {
        sync_with_ring = true;
        clipboard_register = "+";
      };
      highlight = {
        on_yank = true;
        on_put = true;
        timer = 200;
      };
      preserve_cursor_position.enabled = true;
    };
  };

  keymaps = [
    {
      mode = ["n" "x"];
      key = "y";
      action = "<Plug>(YankyYank)";
      options.desc = "Yank text";
    }
    {
      mode = ["n" "x"];
      key = "p";
      action = "<Plug>(YankyPutAfter)";
      options.desc = "Put after cursor";
    }
    {
      mode = ["n" "x"];
      key = "P";
      action = "<Plug>(YankyPutBefore)";
      options.desc = "Put before cursor";
    }
    {
      mode = ["n" "x"];
      key = "gp";
      action = "<Plug>(YankyGPutAfter)";
      options.desc = "Put and move after";
    }
    {
      mode = ["n" "x"];
      key = "gP";
      action = "<Plug>(YankyGPutBefore)";
      options.desc = "Put before and move after";
    }
    {
      mode = "n";
      key = "[y";
      action = "<Plug>(YankyCycleForward)";
      options.desc = "Previous yank";
    }
    {
      mode = "n";
      key = "]y";
      action = "<Plug>(YankyCycleBackward)";
      options.desc = "Next yank";
    }
    {
      mode = "n";
      key = "]p";
      action = "<Plug>(YankyPutIndentAfterLinewise)";
      options.desc = "Put indented after";
    }
    {
      mode = "n";
      key = "[p";
      action = "<Plug>(YankyPutIndentBeforeLinewise)";
      options.desc = "Put indented before";
    }
  ];
}
