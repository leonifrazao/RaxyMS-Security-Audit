"""Tests for :class:`RewardClient`."""

from __future__ import annotations

import hashlib
from datetime import datetime
import unittest

from raxy.rewards.reward_client import RewardClient
from raxy.rewards.reward_session import RewardSession


class RewardClientTests(unittest.TestCase):
    def test_collect_summary_is_deterministic(self) -> None:
        session = RewardSession(
            profile_id="user_123",
            email="user@example.com",
            token="token",
            created_at=datetime.utcnow(),
        )
        client = RewardClient()

        summary = client.collect_summary(session)
        expected_points = int(hashlib.sha1(session.email.encode("utf-8")).hexdigest()[:6], 16) % 500 + 100

        self.assertEqual(summary.points, expected_points)
        self.assertEqual(summary.total_tasks(), summary.completed_tasks + summary.pending_tasks)

        other = client.collect_summary(session)
        self.assertEqual(other, summary)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
