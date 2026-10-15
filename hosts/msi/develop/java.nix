{pkgs, ...}: {
  environment.systemPackages = with pkgs; [
    jdk8
    jdk21
    jdk17
    jdk25
  ];
}
