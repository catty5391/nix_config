{ pkgs, ... }:

{
  home.packages = [
    pkgs.termius
  ];
  xdg.desktopEntries.termius = {
    name = "Termius";
    genericName = "SSH Client";

    exec = "termius --force-device-scale-factor=1.25 %U";

    terminal = false;

    categories = [
      "Network"
      "RemoteAccess"
    ];

    settings = {
      MimeType = "x-scheme-handler/termius;";
    };
  };
}
