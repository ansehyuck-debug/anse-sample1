# To learn more about how to use Nix to configure your environment
# see: https://developers.google.com/idx/guides/customize-idx-env
{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-23.11"; # or "unstable"
  # Use https://search.nixos.org/packages to find packages
  packages = [
    pkgs.nodejs_20
    pkgs.python3
  ];
  # Sets environment variables in the workspace
  env = {
    NEXT_PUBLIC_SUPABASE_URL = "https://bksuhgixknsqzzxahuni.supabase.co";
    NEXT_PUBLIC_SUPABASE_ANON_KEY = "sb_publishable_K47Ui76Xyb5hqjAOqJsbYg_u0ZFJTdf";
  };
  idx = {
    # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
    extensions = [
      # "vscodevim.vim"
      "google.gemini-cli-vscode-ide-companion"
    ];
    # Enable previews and customize configuration
    previews = {
      enable = true;
      previews = {
        web = {
          command = ["python3" "-m" "http.server" "$PORT" "--bind" "0.0.0.0"];
          manager = "web";
        };
      };
    };
    # Workspace lifecycle hooks
    workspace = {
      # Runs when a workspace is first created
      onCreate = {
        # Example: install JS dependencies from NPM
        # npm-install = "npm install";
        # Open editors for the following files by default, if they exist:
        default.openFiles = [ "style.css" "main.js" "index.html" ];
      };
      # Runs when the workspace is (re)started
      onStart = {
        generate-config = "echo \"window.CONFIG_SUPABASE_URL = '$NEXT_PUBLIC_SUPABASE_URL'; window.CONFIG_SUPABASE_ANON_KEY = '$NEXT_PUBLIC_SUPABASE_ANON_KEY';\" > public/config.js";
      };
    };
  };
}