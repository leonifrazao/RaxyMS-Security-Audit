# Configuration Guide

RaxyMS is configured via a `config.yaml` file. This guide explains all available options.

## General Structure

The configuration file is divided into several main sections:

- **APP**: General application settings.
- **EXECUTOR**: Controls how farming tasks are run.
- **PROXY**: Manages proxy connections.
- **API**: External API settings (Supabase, Bing, etc.).
- **LOGGING**: Console output and file logging.
- **SESSION**: Browser automation behavior (User-Agents, specific URLs).
- **BINGFLYOUT**: Specific settings for the Flyout task.

## Detailed Options

### Executor

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `users_file` | string | `users.txt` | Path to the file containing accounts (`email:password`). |
| `max_workers` | int | `4` | Number of concurrent accounts to process. |
| `actions` | list | `[login, flyout, ...]` | List of actions to perform for each account. |
| `retry_attempts` | int | `2` | Number of retries if an action fails. |
| `timeout` | int | `300` | Maximum time (seconds) allowing for a single account task. |

### Proxy

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `enabled` | bool | `true` | Enable or disable proxy usage globally. |
| `country` | string | `US` | ISO 3166-1 alpha-2 country code for proxy filtering. |
| `auto_test` | bool | `true` | Automatically test proxies before using them. |
| `sources` | list | `[webshare, proxylist]` | Sources to fetch proxies from. |

### Session

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `softwares_padrao` | list | `[edge]` | Browsers to simulate (`edge`, `chrome`, `firefox`). |
| `sistemas_padrao` | list | `[windows, linux, macos]` | Operating systems to simulate. |
| `ua_limit` | int | `100` | Number of unique User-Agents to generate. |
| `max_login_attempts` | int | `5` | Maximum retries for login failures. |

### Bing Flyout

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `timeout_short` | int | `5` | Short wait timeout (seconds). |
| `timeout_long` | int | `10` | Long wait timeout (seconds). |
| `max_wait_iterations` | int | `10` | Max iterations to wait for flyout elements. |

### Logging

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `nivel_minimo` | string | `INFO` | Minimum log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `mostrar_tempo` | bool | `true` | Show timestamp in log prefix. |
| `usar_cores` | bool | `true` | Enable colored output in terminal. |

## Example Configuration

```yaml
executor:
  max_workers: 8
  actions:
    - login
    - rewards

proxy:
  enabled: true
  country: BR

session:
  softwares_padrao:
    - edge
  sistemas_padrao:
    - windows

logging:
  nivel_minimo: DEBUG
```
