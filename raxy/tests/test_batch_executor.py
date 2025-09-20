"""Tests covering the orchestration performed by :class:`BatchExecutor`."""

from __future__ import annotations

from datetime import datetime
import unittest

from raxy.accounts.account import Account
from raxy.config.executor_config import ExecutorConfig
from raxy.execution.batch_executor import BatchExecutor
from raxy.rewards.reward_session import RewardSession
from raxy.rewards.reward_summary import RewardSummary


class FakeAccountLoader:
    def __init__(self, accounts: list[Account]) -> None:
        self._accounts = accounts

    def load(self) -> list[Account]:
        return list(self._accounts)


class FakeLoginService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def authenticate(self, account: Account, *, arguments=None) -> RewardSession:
        args = list(arguments or [])
        self.calls.append((account.profile_id, args))
        return RewardSession(
            profile_id=account.profile_id,
            email=account.email,
            token="token",
            created_at=datetime.utcnow(),
        )


class FakeBrowser:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def open_homepage(self, profile_id: str, *, arguments=None) -> None:
        self.calls.append(profile_id)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def collect_summary(self, session: RewardSession) -> RewardSummary:
        self.calls.append(session.profile_id)
        return RewardSummary(points=100, completed_tasks=1, pending_tasks=0)


class BatchExecutorTests(unittest.TestCase):
    def test_normalize_actions(self) -> None:
        actions = BatchExecutor.normalize_actions([" Login ", "OPEN_REWARDS", "login", "", None])  # type: ignore[list-item]
        self.assertEqual(actions, ["login", "open_rewards"])

    def test_run_processes_all_actions(self) -> None:
        account = Account(email="user@example.com", password="secret", profile_id="user_123")
        loader = FakeAccountLoader([account])
        login = FakeLoginService()
        browser = FakeBrowser()
        client = FakeClient()
        config = ExecutorConfig(users_file="dummy", actions=["login", "open_rewards", "sync_rewards"], max_workers=1)

        executor = BatchExecutor(
            config,
            account_loader=loader,
            login_service=login,
            reward_browser=browser,
            reward_client=client,
        )
        results = executor.run()

        self.assertEqual(login.calls, [("user_123", ["--profile=user_123"])])
        self.assertEqual(browser.calls, ["user_123"])
        self.assertEqual(client.calls, ["user_123"])
        self.assertIn("user_123", results)
        self.assertIsInstance(results["user_123"], RewardSummary)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
