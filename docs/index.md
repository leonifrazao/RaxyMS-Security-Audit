# RaxyMS Documentation

Welcome to the official documentation for **RaxyMS**, the advanced CLI automation tool for Microsoft Rewards farming.

## Overview

RaxyMS is designed to act as a robust backend engine for automating rewards collection. It leverages modern Python technologies to provide:

- **Scalability**: Handle dozens of accounts simultaneously.
- **Reliability**: Headless browser automation that mimics real user behavior.
- **Flexibility**: Database-agnostic design (SQLite/Supabase) and proxy support.

## Navigation

- **[Installation Guide](installation.md)**: Setup Python, dependencies, and environment.
- **[Configuration Guide](configuration.md)**: detailed explanation of `config.yaml`.
- **[Usage Guide](usage.md)**: Command-line reference and workflows.
- **[Development Guide](development.md)**: Architecture overview and contribution.

## Quick Start

### Using Nix (Recommended)

```bash
# Clone
git clone https://github.com/your_username/raxyms.git

# Enter Environment
cd raxyms
nix-shell

# Run
python raxy_project/cli.py run
```

### Manual Setup
```bash
# Clone
git clone https://github.com/your_username/raxyms.git

# Install
cd raxyms/raxy_project
pip install .

# Run
python cli.py run
```
