{ ... }:

{
  services.openssh = {
     enable = true;
     ports = [60003];
     openFirewall = true;
     settings = {
       PermitRootLogin = "yes";
       PubkeyAuthentication = "yes";
       PasswordAuthentication = false;
       KbdInteractiveAuthentication = false;
     };
  };
}
