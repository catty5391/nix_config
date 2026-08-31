{
  keymaps = [
    {
      mode = "i";
      key = "jj";
      action = "<Esc>";
      options = {
        silent = true;
        desc = "Exit insert mode";
      };
    }
    {
      mode = "t";
      key = "<Esc><Esc>";
      action = "<C-\\><C-n>";
      options.desc = "Exit terminal mode";
    }

    # Split creation.
    {
      mode = "n";
      key = "<leader>-";
      action = "<cmd>split<cr>";
      options = {
        silent = true;
        desc = "Split window below";
      };
    }
    {
      mode = "n";
      key = "<leader>|";
      action = "<cmd>vsplit<cr>";
      options = {
        silent = true;
        desc = "Split window right";
      };
    }
    {
      mode = "n";
      key = "<leader>ws";
      action = "<cmd>split<cr>";
      options = {
        silent = true;
        desc = "Split window below";
      };
    }
    {
      mode = "n";
      key = "<leader>wv";
      action = "<cmd>vsplit<cr>";
      options = {
        silent = true;
        desc = "Split window right";
      };
    }

    # Window navigation and lifecycle.
    {
      mode = "n";
      key = "<C-h>";
      action = "<C-w>h";
      options.desc = "Go to left window";
    }
    {
      mode = "n";
      key = "<C-j>";
      action = "<C-w>j";
      options.desc = "Go to lower window";
    }
    {
      mode = "n";
      key = "<C-k>";
      action = "<C-w>k";
      options.desc = "Go to upper window";
    }
    {
      mode = "n";
      key = "<C-l>";
      action = "<C-w>l";
      options.desc = "Go to right window";
    }
    {
      mode = "n";
      key = "<leader>ww";
      action = "<C-w>w";
      options.desc = "Switch window";
    }
    {
      mode = "n";
      key = "<leader>wd";
      action = "<cmd>close<cr>";
      options = {
        silent = true;
        desc = "Close window";
      };
    }
    {
      mode = "n";
      key = "<leader>w=";
      action = "<C-w>=";
      options.desc = "Equalize window sizes";
    }

    # Window resizing.
    {
      mode = "n";
      key = "<C-Up>";
      action = "<cmd>resize +2<cr>";
      options = {
        silent = true;
        desc = "Increase window height";
      };
    }
    {
      mode = "n";
      key = "<C-Down>";
      action = "<cmd>resize -2<cr>";
      options = {
        silent = true;
        desc = "Decrease window height";
      };
    }
    {
      mode = "n";
      key = "<C-Left>";
      action = "<cmd>vertical resize -2<cr>";
      options = {
        silent = true;
        desc = "Decrease window width";
      };
    }
    {
      mode = "n";
      key = "<C-Right>";
      action = "<cmd>vertical resize +2<cr>";
      options = {
        silent = true;
        desc = "Increase window width";
      };
    }
  ];
}
