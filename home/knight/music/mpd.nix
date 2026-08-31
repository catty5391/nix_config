{config, pkgs, ...}: let
  musicDirectory = "${config.home.homeDirectory}/music";
in {
  home.packages = with pkgs; [
    mpc
  ];
  services.mpd.enable = true;
  services.mpd = {
    inherit musicDirectory;
    extraConfig = ''
      audio_output {
        type "pipewire"
        name "PipeWire Output"
      }

      restore_paused "yes"
      auto_update "yes"
    '';
  };
  programs.ncmpcpp = {
    enable = true;
    mpdMusicDir = musicDirectory;
    settings = {
      lyrics_directory = musicDirectory;
      store_lyrics_in_song_dir = "yes";
    };
  };
}
