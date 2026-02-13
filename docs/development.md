# Development Guide

This guide is for developers who want to contribute to the RaxyMS codebase or understand its architecture.

## Architecture

RaxyMS follows a **Clean Architecture** approach, separating concerns into distinct layers:

### 1. Domain (`raxy/domain`)
Contains the core business entities (e.g., `Conta`, `Proxy`). These objects have no dependencies on external frameworks or databases.

### 2. Interfaces (`raxy/interfaces`)
Defines the contracts (Abstract Base Classes) for services and repositories. This ensures loose coupling.
- `IContaRepository`: Contract for data access.
- `IProxyService`: Contract for proxy management.

### 3. Services (`raxy/services`)
Implements the business logic.
- `ExecutorService`: Orchestrates the farming process.
- `ProxyService`: Manages proxy lifecycle and testing.

### 4. Infrastructure (`raxy/infrastructure`)
Concrete implementations of interfaces.
- `SQLiteRepository`: Local database access.
- `SupabaseRepository`: Cloud database access.
- `BotasaurusClient`: Browser automation implementation.

## Project Structure

```
raxy_project/
├── app/               # (Legacy/Future) API Layer
├── raxy/              # Core Library
│   ├── container.py   # Dependency Injection Container
│   ├── core/          # Configuration & Utilities
│   ├── domain/        # Business Entities
│   ├── infrastructure/# Implementation Details
│   ├── interfaces/    # Abstract Contracts
│   └── services/      # Business Logic
├── cli.py             # CLI Entry Point
└── config.yaml        # Configuration File
```

## Testing

We use `pytest` for testing.

```bash
# Run all tests
pytest

# Run specific test file
pytest raxy/tests/test_foo.py
```

## Contribution Workflow

1.  **Fork** the repository.
2.  Create a **feature branch** (`git checkout -b feature/my-feature`).
3.  Implement your changes.
4.  Add **unit tests** if applicable.
5.  Run **tests** to ensure no regressions.
6.  Submit a **Pull Request**.
