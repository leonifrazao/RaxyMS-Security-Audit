# Farm Rewards Toolkit

The Farm toolkit provides a clean baseline for experimenting with Microsoft Rewards automations. The focus of this refactor is on
clarity, deterministic behaviour and small composable units.

## Modules Overview

| Area        | Description |
| ----------- | ----------- |
| `accounts`  | Domain layer containing the `Account` dataclass, the `AccountLoader` parser and the `ProfileIdentifier` helper. |
| `config`    | Includes `ExecutorConfig`, responsible for reading environment variables and producing immutable configuration objects. |
| `execution` | Hosts the `BatchExecutor`, which orchestrates login, browser simulation and rewards synchronisation. |
| `logging`   | Provides the `StructuredLogger`, a minimal wrapper around the standard logging module. |
| `rewards`   | Groups the automation services: `RewardLoginService`, `RewardBrowser`, `RewardClient`, `RewardSession` and `RewardSummary`. |
| `tests`     | Contains unit tests covering the main workflows. |

## Execution Flow

1. `AccountLoader` reads the configured credential file and emits `Account` objects.
2. `BatchExecutor` normalises the configured actions (`login`, `open_rewards`, `sync_rewards`).
3. For each account the executor:
   - authenticates via `RewardLoginService` (generating a `RewardSession`),
   - simulates navigation through `RewardBrowser`,
   - collects deterministic summaries through `RewardClient` and returns the `RewardSummary` objects.
4. The executor returns a dictionary mapping each profile identifier to its summary, making it trivial to consume the results programmatically.

## Environment Variables

| Variable            | Purpose |
| ------------------- | ------- |
| `USERS_FILE`        | Path to the credential file (`users.txt` by default). |
| `ACTIONS`           | Comma separated action names. Unknown actions are ignored. |
| `MAX_WORKERS`       | Maximum number of worker threads. |
| `RAXY_MAX_WORKERS`  | Alternative variable name kept for compatibility. |

## Logging

`StructuredLogger` keeps messages concise while attaching contextual key-value pairs. Custom loggers can be created with
`StructuredLogger().bind(component="executor")`, ensuring every message includes the defined metadata.

## Testing

Run the full suite with:

```bash
python -m unittest discover
```

The tests avoid external dependencies and run in milliseconds, providing quick feedback for future changes.

## Extending the Toolkit

- Add new actions by extending `BatchExecutor` and updating the normalisation step.
- Replace `RewardClient` with an implementation that calls real services if necessary; the deterministic version is intended for local experiments and testing.
- Introduce alternative logging strategies by implementing the same interface exposed by `StructuredLogger` (`info`, `success`, `warning`, `error`).

This documentation reflects the refactored architecture and should be kept aligned with future improvements.
