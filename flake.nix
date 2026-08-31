{
  description = "Reproducible NixOS, Niri, Noctalia and Nixvim configuration";

  nixConfig = {
    substituters = [
      "https://mirrors.tuna.tsinghua.edu.cn/nix-channels/store"
      "https://cache.nixos.org"
      "https://nix-community.cachix.org"
      "https://cook-nixvim.cachix.org"
    ];
    trusted-public-keys = [
      "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
      "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
      "cook-nixvim.cachix.org-1:LjCZ3VSYrcwTQxHpd834EIswdkfHoSd/EsKUYLRruF4="
    ];
  };

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    nixpkgs-unstable.url = "github:nixos/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager/release-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    noctalia = {
      url = "github:noctalia-dev/noctalia-shell";
      inputs.nixpkgs.follows = "nixpkgs-unstable";
    };

    nyxniri = {
      url = "github:ech678/NyxNiri/2e32d0aa1e8f10efad478bab5c24e750672ada86";
      flake = false;
    };

    noctalia-plugins = {
      url = "github:noctalia-dev/official-plugins";
      flake = false;
    };

    fcitx5-candlelight = {
      url = "github:thep0y/fcitx5-themes-candlelight";
      flake = false;
    };

    catppuccin.url = "github:catppuccin/nix/release-26.05";
    CookNixvim.url = "github:Youthdreamer/CookNixvim";
  };

  outputs = inputs @ {
    nixpkgs,
    nixpkgs-unstable,
    home-manager,
    catppuccin,
    CookNixvim,
    noctalia,
    fcitx5-candlelight,
    ...
  }: let
    system = "x86_64-linux";
    username = "knight";

    mkHost = hostModule:
      nixpkgs.lib.nixosSystem {
        inherit system;

        specialArgs = {
          inherit inputs username;
          pkgs-unstable = import nixpkgs-unstable {
            inherit system;
            config.allowUnfree = true;
          };
        };

        modules = [
          hostModule
          catppuccin.nixosModules.catppuccin
          home-manager.nixosModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.extraSpecialArgs = {
              inherit inputs username;
              pkgs-unstable = import nixpkgs-unstable {
                inherit system;
                config.allowUnfree = true;
              };
            };
            home-manager.users.${username}.imports = [
              catppuccin.homeModules.catppuccin
              noctalia.homeModules.default
              ./home/knight
            ];
          }
        ];
      };
  in {
    nixosConfigurations.nas-linux = mkHost ./hosts/nas-linux;
    nixosConfigurations.msi = mkHost ./hosts/msi;
    # Keep the previous selector working during migration.
  };
}
