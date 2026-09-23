{
  pkgs,
  username,
  ...
}: {
  programs.wireshark = {
    enable = true;
    package = pkgs.wireshark;
    dumpcap.enable = true;
  };

  environment.systemPackages = [pkgs.snitch];

  home-manager.users.${username} = {config, lib, ...}: {
    # Keep preferences writable so changes made in Wireshark can still be saved.
    home.activation.wiresharkDarkMode = lib.hm.dag.entryAfter ["writeBoundary"] ''
      run ${pkgs.python3}/bin/python3 - ${lib.escapeShellArg "${config.xdg.configHome}/wireshark/preferences"} <<'PY'
      import pathlib
      import re
      import sys

      path = pathlib.Path(sys.argv[1])
      text = path.read_text() if path.exists() else ""
      text = re.sub(r"(?m)^#?gui\.color_scheme:.*\n?", "", text)
      text = text.rstrip("\n") + "\ngui.color_scheme: dark\n"
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(text)
      PY
    '';
  };
}
