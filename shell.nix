{ pkgs ? import <nixpkgs> { config.allowUnfree = true; } }:
let
  version = "311";
  python = pkgs."python${pkgs.lib.versions.majorMinor version}";
  qt = pkgs.libsForQt5; # garante consistência Qt + PyQt
  burpsuite = pkgs.callPackage ./utils/burp.nix {};
  nodejs = pkgs.nodejs_22; # ambiente Node.js moderno para Next.js
  runtimeLibs = with pkgs; [
    stdenv.cc.cc.lib   # <-- provides libstdc++.so.6
    glibc              # libc.so.6, ld-linux, etc.
    zlib
    libglvnd           # OpenGL loader (often needed by Chrome/Qt)
    libGLU
    xorg.libX11
    webkitgtk_4_1      # <-- ADICIONADO: Fornece a biblioteca para o shotgun-code
  ];
in
pkgs.mkShell {
  venvDir = ".venv";
  packages = (with python.pkgs; [
    venvShellHook
    pip
    # pyqt5
    # opencv4
    # python-uinput
    # evdev
  ]) ++ (with pkgs; [
    # Toolchain
    gcc gnumake 
    cmake 
    pkg-config 
    extra-cmake-modules
    stdenv.cc.cc.lib
    zlib 
    zlib.dev

    # OpenGL + Mesa
    libglvnd libGLU mesa
    
    # X11 core
    xorg.libX11 xorg.libXext xorg.libXrender xorg.libXtst xorg.libXi
    xorg.libXrandr xorg.libXcursor xorg.libXdamage xorg.libXfixes
    xorg.libXxf86vm xorg.libxcb xorg.libSM xorg.libICE xorg.libxkbfile
    xorg.libXcomposite xorg.libXinerama
    
    # XCB utils
    xorg.xcbutilkeysyms xorg.xcbutilwm xorg.xcbutilimage
    xorg.xcbutilrenderutil xcb-util-cursor

    xdotool
    
    # Qt stack
    qt.qtbase qt.qtwayland qt.qtsvg
    
    # Extra deps
    libxkbcommon dbus fontconfig freetype
    
    # Backend alternativo
    gtk2-x11 gtk2

    chromium
    chromedriver

    # ffmpeg

    nodejs
    pnpm

    jdk

    xray
    windsurf
  ]) ++ [
    burpsuite
  ];

  shellHook = ''
    export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath runtimeLibs}:''${LD_LIBRARY_PATH:-}"
    alias burp_crack='java -jar loader.jar & burpsuitepro &'
    alias codex='npx @openai/codex'
    export PNPM_HOME="$PWD/.pnpm"
    mkdir -p "$PNPM_HOME"
    export PATH="$PNPM_HOME:$PATH"

    primeiro_setup=false
    if [ ! -d "$venvDir" ]; then
      echo "[Raxy] Criando ambiente virtual em $venvDir"
      python -m venv "$venvDir"
      primeiro_setup=true
    fi

    source "$venvDir/bin/activate"

    if [ "$primeiro_setup" = true ] || [ ! -f "$venvDir/.deps-instaladas" ]; then
      echo "[Raxy] Instalando dependências do requirements.txt"
      if [ -f requirements.txt ]; then
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install -e ./raxy_project/raxy
      else
          echo "[Raxy] Aviso: requirements.txt não encontrado, nenhuma dependência instalada"
      fi
      touch "$venvDir/.deps-instaladas"
      echo "[Raxy] Ambiente pronto!"
    fi
  '';


  postShellHook = ''
    # export QT_QPA_PLATFORM="xcb"
    # export QT_PLUGIN_PATH="${qt.qtbase}/lib/qt-${qt.qtbase.version}/plugins"
    # export QT_QPA_PLATFORM_PLUGIN_PATH="${qt.qtbase}/lib/qt-${qt.qtbase.version}/plugins/platforms"
    # export GDK_BACKEND=x11
    # export CLUTTER_BACKEND=x11
    # export SDL_VIDEODRIVER=x11
    # export OPENCV_GUI_BACKEND=GTK
    # export DISPLAY=''${DISPLAY:-:0}
    # export HSA_OVERRIDE_GFX_VERSION=10.3.0
    # export HSA_ENABLE_SDMA=0
    # export ROC_ENABLE_PRE_VEGA=1
    # export LIBGL_ALWAYS_SOFTWARE=0
    # export __GLX_VENDOR_LIBRARY_NAME=mesa
  '';
}
