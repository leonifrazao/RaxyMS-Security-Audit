"""Aggregate information collected from the rewards service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RewardSummary:
    """Lightweight value object describing points and task status."""

    points: int
    completed_tasks: int
    pending_tasks: int

    def total_tasks(self) -> int:
        """Return the total amount of tracked tasks."""

        return self.completed_tasks + self.pending_tasks


__all__ = ["RewardSummary"]
