"""Configuration values used by the batch executor."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import List

from ..utils.environment_reader import EnvironmentReader

DEFAULT_USERS_FILE = "users.txt"
DEFAULT_ACTIONS: List[str] = ["login", "open_rewards", "sync_rewards"]
DEFAULT_MAX_WORKERS = 1


@dataclass(slots=True)
class ExecutorConfig:
    """Container for execution parameters derived from environment variables."""

    users_file: str = DEFAULT_USERS_FILE
    actions: List[str] = field(default_factory=lambda: list(DEFAULT_ACTIONS))
    max_workers: int = DEFAULT_MAX_WORKERS

    @classmethod
    def from_environment(cls) -> "ExecutorConfig":
        """Build a configuration instance using environment variables."""

        users_file = os.getenv("USERS_FILE", DEFAULT_USERS_FILE)
        actions = EnvironmentReader.as_list("ACTIONS") or list(DEFAULT_ACTIONS)
        max_workers = EnvironmentReader.as_int("MAX_WORKERS")
        if max_workers is None:
            max_workers = EnvironmentReader.as_int("RAXY_MAX_WORKERS")
        max_workers = max(max_workers or DEFAULT_MAX_WORKERS, 1)
        return cls(users_file=users_file, actions=actions, max_workers=max_workers)

    def clone(self) -> "ExecutorConfig":
        """Return a safe copy so mutable fields can be altered freely."""

        return ExecutorConfig(
            users_file=self.users_file,
            actions=list(self.actions),
            max_workers=self.max_workers,
        )


__all__ = [
    "ExecutorConfig",
    "DEFAULT_USERS_FILE",
    "DEFAULT_ACTIONS",
    "DEFAULT_MAX_WORKERS",
]
