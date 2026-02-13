# Installation Guide

## System Requirements

- **Operating System**: Linux (recommended), Windows, or macOS.
- **Python**: Version 3.10 or higher.
- **Git**: For version control.
- **Xray / V2Ray**: (Optional) For proxy tunnel management.

## Step-by-Step Installation

### Option 1: Using Nix (Recommended)

RaxyMS includes a `shell.nix` file that defines a reproducible development environment with all necessary dependencies (Python 3.10, libraries, and tools).

1.  **Install Nix**: Follow the instructions at [nixos.org/download](https://nixos.org/download.html).

2.  **Clone the Repository**:
    ```bash
    git clone https://github.com/leonifrazao/MSRewardsFarm.git
    cd MSRewardsFarm
    ```

3.  **Enter the Environment**:
    Run the following command in the project root:
    ```bash
    nix-shell
    ```

    This will:
    - Download and configure Python 3.10.
    - Create a virtual environment `.venv` automatically.
    - Install all Python dependencies.
    - Setup system libraries `glib`, `zlib`, `stdenv` (crucial for headless browsers).
    - Provide `xray` and `google-chrome` available in the path.

    Once inside the shell, you can run `python raxy_project/cli.py` directly.

### Option 2: Manual Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/leonifrazao/MSRewardsFarm.git
cd MSRewardsFarm/raxy_project
```

#### 2. Set up Python Environment

It is recommended to use a virtual environment to avoid conflicts.

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
```

### 3. Install Dependencies

You can install the package in editable mode (recommended for development) or just the requirements.

```bash
pip install -r requirements.txt
# OR
pip install -e .
```

### 4. Verify Installation

Run the help command to ensure the CLI is accessible.

```bash
python cli.py --help
```

## Proxy Setup (Optional)

If you plan to use proxies, you need a V2Ray or Xray executable.

1.  Download the core executable for your OS from [Xray-core releases](https://github.com/XTLS/Xray-core/releases).
2.  Extract the archive.
3.  Ensure `xray` (or `v2ray`) is in your system PATH, or place it in a known location and update your configuration if necessary (the system usually looks in PATH).
