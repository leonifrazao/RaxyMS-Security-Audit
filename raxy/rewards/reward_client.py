"""Client used to derive deterministic rewards information from a session."""

from __future__ import annotations

import hashlib

from ..loggers.structured_logger import StructuredLogger
from .reward_session import RewardSession
from .reward_summary import RewardSummary


class RewardClient:
    """Generate predictable summaries for demonstration and tests."""

    def __init__(self, logger: StructuredLogger | None = None) -> None:
        self._logger = (logger or StructuredLogger()).bind(service="rewards")

    def collect_summary(self, session: RewardSession) -> RewardSummary:
        """Return a :class:`RewardSummary` derived from the session data."""

        digest = hashlib.sha1(session.email.encode("utf-8")).hexdigest()
        points = int(digest[:6], 16) % 500 + 100
        completed = int(digest[6:8], 16) % 10
        pending = int(digest[8:10], 16) % 5
        summary = RewardSummary(points=points, completed_tasks=completed, pending_tasks=pending)
        self._logger.success(
            "Rewards summary collected",
            profile=session.profile_id,
            points=summary.points,
            completed=summary.completed_tasks,
            pending=summary.pending_tasks,
        )
        return summary


__all__ = ["RewardClient"]
