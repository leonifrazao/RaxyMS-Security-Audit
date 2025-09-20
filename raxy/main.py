"""Command line entry point for the Farm rewards automation."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:  # pragma: no cover - runtime convenience
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from raxy.execution.batch_executor import BatchExecutor


def main() -> None:
    """Run the batch executor with configuration inferred from the environment."""

    BatchExecutor().run()


if __name__ == "__main__":  # pragma: no cover
    main()
