{pkgs, ...}: let
  seu-autologin = pkgs.writeShellApplication {
    name = "seu-autologin";

    runtimeInputs = with pkgs; [
      curl
      jq
      networkmanager
      iputils
      coreutils
    ];

    text = ''
      log() {
        printf '%s\n' "$*"
      }

      if [[ -z "''${ID:-}" || -z "''${PASSWORD:-}" ]]; then
        log "[Error] /etc/seu-autologin.env must define ID and PASSWORD"
        exit 1
      fi

      curl_direct() {
        curl -k --noproxy '*' -sS --fail \
          --connect-timeout 5 --max-time 15 "$@"
      }

      check_wifi() {
        local networks active ssid
        if ! networks=$(nmcli -t -f IN-USE,SSID device wifi list --rescan no); then
          return 1
        fi
        while IFS=: read -r active ssid; do
          if [[ "$active" == '*' && "$ssid" == 'SEU-WLAN' ]]; then
            return 0
          fi
        done <<< "$networks"
        return 1
      }

      parse_jsonp() {
        local pattern='^[[:space:]]*dr1003[[:space:]]*\((.*)\)[[:space:]]*;?[[:space:]]*$'
        [[ "$1" =~ $pattern ]] || return 1
        printf '%s' "''${BASH_REMATCH[1]}" |
          jq -cse 'if length == 1 and (.[0] | type == "object") then .[0] else empty end' 2>/dev/null
      }

      login_wlan() {
        local response status ip result
        # The network may have changed while the connectivity check was running.
        check_wifi || return 1
        if ! response=$(curl_direct 'https://w.seu.edu.cn/drcom/chkstatus?callback=dr1003'); then
          log "[Error] Cannot fetch campus status; retrying in 30 seconds"
          return 1
        fi
        if ! status=$(parse_jsonp "$response"); then
          log "[Error] Invalid campus status JSONP; retrying in 30 seconds"
          return 1
        fi
        if ! ip=$(jq -er '
          .v46ip | select(type == "string") |
          select(test("^([0-9]{1,3}\\.){3}[0-9]{1,3}$")) |
          select(split(".") | all(tonumber <= 255)) |
          select(. != "0.0.0.0")
        ' <<< "$status" 2>/dev/null); then
          log "[Error] Campus status contains no valid IPv4 address"
          return 1
        fi

        # Never submit credentials after switching away from the campus SSID.
        check_wifi || return 1
        if ! response=$(
          curl_direct -G 'https://w.seu.edu.cn:801/eportal/' \
            --data-urlencode 'c=Portal' \
            --data-urlencode 'a=login' \
            --data-urlencode 'callback=dr1003' \
            --data-urlencode 'login_method=1' \
            --data-urlencode "user_account=,0,$ID" \
            --data-urlencode "user_password=$PASSWORD" \
            --data-urlencode "wlan_user_ip=$ip"
        ); then
          log "[Error] Campus login request failed; retrying in 30 seconds"
          return 1
        fi
        if ! result=$(parse_jsonp "$response"); then
          log "[Error] Invalid campus login JSONP; retrying in 30 seconds"
          return 1
        fi
        if ! jq -e '.result == 1 or .result == "1"' <<< "$result" >/dev/null 2>&1; then
          log "[Error] Campus authentication was not accepted; retrying in 30 seconds"
          return 1
        fi
        log "[Success] Campus authentication accepted"
      }

      log "[Begin] Campus autologin service started"
      last_state=unknown
      while true; do
        if ! check_wifi; then
          if [[ "$last_state" != waiting ]]; then
            log "[WLAN] Waiting for SEU-WLAN"
          fi
          last_state=waiting
        elif ping -c 1 -W 3 baidu.com >/dev/null 2>&1; then
          if [[ "$last_state" != online ]]; then
            log "[Online] Internet connectivity check passed"
          fi
          last_state=online
        else
          log "[Trial] Internet unavailable; attempting campus authentication"
          if login_wlan; then
            last_state=authenticated
          else
            last_state=failed
          fi
        fi
        sleep 30
      done
    '';
  };
in {
  systemd.services.seu-autologin = {
    description = "SEU WLAN AUTO LOGIN";

    wantedBy = ["multi-user.target"];

    after = [
      "NetworkManager.service"
      "network-online.target"
    ];

    wants = [
      "network-online.target"
    ];

    serviceConfig = {
      Type = "simple";

      ExecStart = "${seu-autologin}/bin/seu-autologin";
      EnvironmentFile = "/etc/seu-autologin.env";

      Restart = "always";
      RestartSec = 5;

      User = "root";
    };
  };
}
