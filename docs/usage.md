# Usage Guide

This guide covers the most common commands and workflows for RaxyMS.

All commands are executed via the `cli.py` script.

## Basic Commands

> [!TIP]
> **Using Nix?** Ensure you are inside the `nix-shell` environment before running these commands to have all dependencies loaded.

### Running a Farm

To start the farming process for all configured accounts using the default settings:

```bash
python cli.py run
```

### Running for a Single Account

You can run the farm for a specific account without modifying your database or users file. This is useful for testing or debugging a specific login.

```bash
python cli.py run --email user@example.com --password mysecurepassword
```

**Options:**
- `--proxy-uri`: Specify a proxy string (e.g., `http://user:pass@host:port`) to use for this run.
- `--no-proxy`: Disable proxy usage for this run.

### Importing Accounts

Import accounts from a text file into the database. The file format must be `email:password` (one per line).

```bash
python cli.py accounts import users.txt
```

**Options:**
- `--target`: Specify destination (`local` for SQLite or `cloud` for Supabase).

### Listing Accounts

View all accounts currently stored in the database.

```bash
python cli.py accounts list
```

## Proxy Management

### Testing Proxies

Test the validity and speed of your configured proxies.

```bash
python cli.py proxy test --threads 20 --country US
```

### Starting Proxy Bridge

Manually start the local proxy bridge (useful if you want to inspect traffic or debug connection issues).

```bash
python cli.py proxy start
```

## Advanced Workflows

### Batch Processing with Custom Workers

If you have a powerful machine and many proxies, you can increase the concurrency:

```bash
python cli.py run --workers 16
```

### Cloud Sync Workflow

1.  Configure Supabase credentials in `.env`.
2.  Import accounts to cloud:
    ```bash
    python cli.py accounts import users.txt --target cloud
    ```
3.  Run farm using cloud source:
    ```bash
    python cli.py run --source cloud
    ```
