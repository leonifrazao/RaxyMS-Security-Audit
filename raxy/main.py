"""Command line entry point for the Farm rewards automation."""

from __future__ import annotations

from .execution.batch_executor import BatchExecutor


def main() -> None:
    """Run the batch executor with configuration inferred from the environment."""

    BatchExecutor().run()


if __name__ == "__main__":  # pragma: no cover
    main()
