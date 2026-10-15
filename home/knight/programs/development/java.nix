{pkgs, ...}: let
  jdks = {
    jdk8 = pkgs.jdk8;
    jdk17 = pkgs.jdk17;
    jdk21 = pkgs.jdk21;
    jdk25 = pkgs.jdk25;
  };

  # Only one JDK can provide the unversioned java/javac commands in the
  # Home Manager profile. Change this line to select another default.
  defaultJdk = jdks.jdk17;
in {
  programs.java = {
    enable = true;
    package = defaultJdk;
  };

  # Keep every JDK available at a stable path without merging their
  # conflicting bin directories into the Home Manager profile.
  home.file = {
    ".jdks/jdk8".source = jdks.jdk8.home;
    ".jdks/jdk17".source = jdks.jdk17.home;
    ".jdks/jdk21".source = jdks.jdk21.home;
    ".jdks/jdk25".source = jdks.jdk25.home;
  };

  home.sessionVariables = {
    JAVA_HOME_8 = "${jdks.jdk8.home}";
    JAVA_HOME_17 = "${jdks.jdk17.home}";
    JAVA_HOME_21 = "${jdks.jdk21.home}";
    JAVA_HOME_25 = "${jdks.jdk25.home}";
  };
}
