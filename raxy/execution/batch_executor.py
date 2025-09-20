"""High level orchestration for processing multiple accounts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Tuple

from ..accounts.account import Account
from ..accounts.account_loader import AccountLoader
from ..config.executor_config import DEFAULT_ACTIONS, ExecutorConfig
from ..loggers.structured_logger import StructuredLogger
from ..rewards.reward_browser import RewardBrowser
from ..rewards.reward_client import RewardClient
from ..rewards.reward_login_service import RewardLoginService
from ..rewards.reward_session import RewardSession
from ..rewards.reward_summary import RewardSummary


class BatchExecutor:
    """Coordinate the login and rewards synchronization for all accounts."""

    def __init__(
        self,
        config: ExecutorConfig | None = None,
        *,
        logger: StructuredLogger | None = None,
        account_loader: AccountLoader | None = None,
        login_service: RewardLoginService | None = None,
        reward_browser: RewardBrowser | None = None,
        reward_client: RewardClient | None = None,
    ) -> None:
        self._config = (config.clone() if config else ExecutorConfig.from_environment())
        self._logger = (logger or StructuredLogger()).bind(component="executor")
        self._loader = account_loader or AccountLoader(self._config.users_file)
        self._login_service = login_service or RewardLoginService(self._logger)
        self._reward_browser = reward_browser or RewardBrowser(self._logger)
        self._reward_client = reward_client or RewardClient(self._logger)
        self._actions = self.normalize_actions(self._config.actions) or list(DEFAULT_ACTIONS)

    @staticmethod
    def normalize_actions(actions: Iterable[str]) -> List[str]:
        """Normalize action names removing blanks and duplications."""

        normalized: List[str] = []
        for action in actions:
            if not isinstance(action, str):
                continue
            cleaned = action.strip().lower()
            if not cleaned or cleaned in normalized:
                continue
            normalized.append(cleaned)
        return normalized

    def run(self) -> Dict[str, RewardSummary]:
        """Execute the configured actions for each account and return summaries."""

        try:
            accounts = self._loader.load()
        except FileNotFoundError:
            self._logger.error("Account file not found", path=self._config.users_file)
            return {}

        if not accounts:
            self._logger.warning("No accounts available", path=self._config.users_file)
            return {}

        self._logger.info("Processing accounts", total=len(accounts), actions=self._actions)
        results: Dict[str, RewardSummary] = {}

        if self._config.max_workers <= 1 or len(accounts) <= 1:
            for account in accounts:
                profile, summary = self._process_account(account)
                if summary:
                    results[profile] = summary
            return results

        workers = max(1, min(self._config.max_workers, len(accounts)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._process_account, account): account for account in accounts}
            for future in as_completed(futures):
                profile, summary = future.result()
                if summary:
                    results[profile] = summary
        return results

    def _process_account(self, account: Account) -> Tuple[str, RewardSummary | None]:
        """Run every action for a single account and return the summary."""

        account_logger = self._logger.bind(email=account.masked_email(), profile=account.profile_id)
        account_logger.info("Starting account processing")
        session: RewardSession | None = None
        summary: RewardSummary | None = None

        for action in self._actions:
            if action == "login":
                session = self._handle_login(account, account_logger)
            elif action == "open_rewards":
                self._handle_open_rewards(account, account_logger)
            elif action == "sync_rewards":
                summary = self._handle_sync_rewards(account, session, account_logger)
            else:
                account_logger.warning("Unknown action skipped", action=action)

        if summary:
            account_logger.info(
                "Account finished",
                points=summary.points,
                completed=summary.completed_tasks,
                pending=summary.pending_tasks,
            )
        else:
            account_logger.info("Account finished without summary")

        return account.profile_id, summary

    def _handle_login(self, account: Account, logger: StructuredLogger) -> RewardSession:
        """Execute the login flow and return an authenticated session."""

        arguments = [f"--profile={account.profile_id}"]
        return self._login_service.authenticate(account, arguments=arguments)

    def _handle_open_rewards(self, account: Account, logger: StructuredLogger) -> None:
        """Simulate opening the rewards homepage for observability."""

        self._reward_browser.open_homepage(account.profile_id, arguments=[account.profile_id])

    def _handle_sync_rewards(
        self,
        account: Account,
        session: RewardSession | None,
        logger: StructuredLogger,
    ) -> RewardSummary | None:
        """Collect the rewards summary if a session is available."""

        if session is None:
            logger.warning("Skipping rewards synchronization because login was skipped")
            return None
        return self._reward_client.collect_summary(session)


__all__ = ["BatchExecutor"]
