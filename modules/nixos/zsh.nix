{ pkgs, ... }:

{
  programs.zsh = {
    enable = true;
    enableCompletion = true;
    syntaxHighlighting.enable = true;

    # aliases、历史记录、autosuggestions 等配置
    histSize = 10000;
    histFile = "$HOME/.zsh_history";

    setOptions = [
      "HIST_IGNORE_DUPS"
      "HIST_IGNORE_ALL_DUPS"
      "SHARE_HISTORY"
      "HIST_FCNTL_LOCK"
      "AUTO_CD"
      "INTERACTIVE_COMMENTS"
    ];

    shellAliases = {
      ll = "ls -lah";
      la = "ls -A";
      l = "ls -CF";
      rebuild = "sudo nixos-rebuild switch --flake /etc/nixos#msi";
      docker-ps = "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'";
    };

    interactiveShellInit = ''
      bindkey -e

      # 根据历史输入显示灰色建议，按右方向键接受。
      source ${pkgs.zsh-autosuggestions}/share/zsh-autosuggestions/zsh-autosuggestions.zsh
    '';
  };

  programs.starship = {
    enable = true;
    presets = [ "nerd-font-symbols" ];

    settings = {
      # 主题配置
      add_newline = false;
      command_timeout = 1000;

      username = {
        show_always = true;
        style_user = "bold green";
        style_root = "bold red";
        format = "[$user]($style)";
      };

      hostname = {
        ssh_only = true;
        style = "bold green";
        format = "[@$hostname]($style) ";
      };

      directory = {
        style = "bold blue";
        truncation_length = 4;
        truncate_to_repo = false;
      };

      git_branch = {
        symbol = " ";
        style = "bold purple";
      };

      git_status = {
        style = "bold yellow";
      };

      java = {
        symbol = " ";
        style = "bold red";
      };

      nix_shell = {
        symbol = "❄ ";
        style = "bold cyan";
        format = "via [$symbol$state]($style) ";
      };

      docker_context = {
        symbol = " ";
        style = "bold blue";
      };

      character = {
        success_symbol = "[❯](bold green)";
        error_symbol = "[❯](bold red)";
      };
    };
  };

  environment.systemPackages = with pkgs; [
    zsh-autosuggestions
  ];

  users.users.root.shell = pkgs.zsh;
  users.users.knight.shell = pkgs.zsh;
}
