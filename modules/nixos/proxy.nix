{...}: let
  noProxy = "localhost,127.0.0.1,::1,192.168.5.155,.local,seu.edu.cn,.seu.edu.cn";
in {
  networking.proxy = {
    default = "http://127.0.0.1:7890";
    httpProxy = "http://127.0.0.1:7890";
    httpsProxy = "http://127.0.0.1:7890";

    inherit noProxy;
  };
  environment.sessionVariables = {
    HTTP_PROXY = "http://127.0.0.1:7890";
    HTTPS_PROXY = "http://127.0.0.1:7890";

    NO_PROXY = noProxy;
  };
}
