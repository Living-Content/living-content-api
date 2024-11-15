{
  description = "Living Content";
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = inputs @ { self, ... }:
    (inputs.flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import inputs.nixpkgs { inherit system; };
        deps = with pkgs; [
          python310
          wget
        ];
      in
      {
        devShells = {
          default = pkgs.mkShell {
            buildInputs = deps;
            shellHook = ''
              export RUST_LOG="hyper=warn,tracing=warn,eqty_sdk_core::integrity::statements=debug,default=trace"

              configured=$(test -d "./venv")

              if ! $configured; then
                  echo "Creating venv"
                  python -m venv venv
              fi

              #source venv/bin/activate

              if ! $configured; then
                  pip install -Ur requirements/requirements.txt --no-cache-dir
                  ./lc.sh setup:ssl-dev
              fi
            '';
          };

        };
      }
    ));
}
