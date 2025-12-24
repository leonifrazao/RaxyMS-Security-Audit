{ pkgs ? import <nixpkgs> { config.allowUnfree = true; } }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python310
    python310Packages.pip
    python310Packages.virtualenv
    xray
    google-chrome
    chromedriver
    stdenv.cc.cc.lib
    zlib
    glib
  ];

  shellHook = ''
    export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib:${pkgs.glib.out}/lib:$LD_LIBRARY_PATH"
    
    if [ ! -d ".venv" ]; then
      echo "Creating virtual environment..."
      python -m venv .venv
    fi
    
    source .venv/bin/activate
    
    echo "Installing/Updating dependencies..."
    pip install -e ./raxy_project
    
    echo "Environment loaded"
    echo "Python version: $(python --version)"
    echo "Xray version: $(xray -version 2>/dev/null || echo 'check manually')"
  '';
}
