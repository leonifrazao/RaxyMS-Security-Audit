{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python310
    python310Packages.pip
    python310Packages.virtualenv
    xray
    stdenv.cc.cc.lib
    zlib
    glib
  ];

  shellHook = ''
    export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib:${pkgs.glib.out}/lib:$LD_LIBRARY_PATH"
    
    echo "Environment loaded"
    echo "Python version: $(python --version)"
    echo "Xray version: $(xray -version 2>/dev/null || echo 'check manually')"
    echo "To install python dependencies: python -m venv .venv && source .venv/bin/activate && pip install -e raxy_project"
  '';
}
