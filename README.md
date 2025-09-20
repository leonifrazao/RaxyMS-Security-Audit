# Farm Rewards Automation

This repository contains a compact and fully refactored toolkit for orchestrating Microsoft Rewards automation flows. The codebase
is organised around small, well-defined classes to keep each responsibility isolated and easy to understand.

## Features

- Deterministic account loading from a plain text credential file.
- Configurable batch executor with optional multi-thread processing.
- Lightweight structured logging with contextual metadata.
- Self-contained rewards client that produces predictable summaries for testing.
- Zero external Python dependencies.

## Project Layout

```
.
├── raxy/
│   ├── __init__.py               # Public exports
│   ├── main.py                   # CLI entry point
│   ├── accounts/                 # Account domain objects
│   │   ├── account.py            # `Account` dataclass
│   │   ├── account_loader.py     # `AccountLoader` file parser
│   │   └── profile_identifier.py # `ProfileIdentifier` helper
│   ├── config/                   # Configuration objects
│   │   └── executor_config.py    # `ExecutorConfig`
│   ├── execution/                # Orchestrators
│   │   └── batch_executor.py     # `BatchExecutor`
│   ├── loggers/                  # Logging helpers
│   │   └── structured_logger.py  # `StructuredLogger`
│   ├── rewards/                  # Rewards related services
│   │   ├── reward_browser.py     # `RewardBrowser`
│   │   ├── reward_client.py      # `RewardClient`
│   │   ├── reward_login_service.py # `RewardLoginService`
│   │   ├── reward_session.py     # `RewardSession`
│   │   └── reward_summary.py     # `RewardSummary`
│   └── tests/                    # Unit tests (`unittest` based)
├── requirements.txt              # Empty on purpose (standard library only)
└── README.md                     # Project overview
```

## Quick Start

1. Ensure Python 3.11 or newer is installed.
2. Create a `users.txt` file with one `email:password` entry per line.
3. Export optional environment variables:
   - `USERS_FILE`: path to the credential file (defaults to `users.txt`).
   - `ACTIONS`: comma separated actions (`login`, `open_rewards`, `sync_rewards`).
   - `MAX_WORKERS` or `RAXY_MAX_WORKERS`: number of parallel workers.
4. Execute the CLI:

```bash
python -m raxy.main
```

The executor logs structured messages describing the progress for each account. The returned summaries are available by using the
API programmatically:

```python
from raxy import BatchExecutor

summaries = BatchExecutor().run()
for profile, summary in summaries.items():
    print(profile, summary.points)
```

## Running Tests

```bash
python -m unittest discover
```

The suite covers account parsing, executor orchestration and the deterministic behaviour of the rewards client.

## Coding Guidelines

- Each module exposes exactly one class to keep responsibilities minimal.
- Function and class names use English terms and remain short.
- Business logic is intentionally deterministic to simplify validation and test automation.
- Logging happens through `StructuredLogger`, which can be extended or replaced as needed.

## Contributing

1. Fork the repository and create a feature branch.
2. Add or update unit tests whenever behaviour changes.
3. Run `python -m unittest discover` before submitting a pull request.

Enjoy the cleaner codebase!
