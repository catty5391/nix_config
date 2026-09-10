{
  plugins = {
    colorful-winsep.enable = true;
    smear-cursor = {
      enable = true;
      settings = {
        smear_between_buffers = true;
        smear_between_neighbor_lines = true;
        scroll_buffer_space = true;
        smear_insert_mode = true;
        stiffness = 0.6;
        trailing_stiffness = 0.4;
        damping = 0.85;
      };
    };
  };
}
