{...}: {
  networking.proxy = {
    default = "http://127.0.0.1:7890";
    httpProxy = "http://127.0.0.1:7890";
    httpsProxy = "http://127.0.0.1:7890";

    noProxy = "localhost,127.0.0.1,::1,192.168.5.155";
  };
  environment.sessionVariables = {
    HTTP_PROXY = "http://127.0.0.1:7890";
    HTTPS_PROXY = "http://127.0.0.1:7890";

    NO_PROXY = "localhost,127.0.0.1,::1,*.local";
  };
}
