"""Service responsible for creating authenticated sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence
from uuid import uuid4

from ..accounts.account import Account
from ..logging.structured_logger import StructuredLogger
from .reward_session import RewardSession


class RewardLoginService:
    """Perform a simplified authentication flow for an :class:`Account`."""

    def __init__(self, logger: StructuredLogger | None = None) -> None:
        self._logger = (logger or StructuredLogger()).bind(service="login")

    def authenticate(self, account: Account, *, arguments: Sequence[str] | None = None) -> RewardSession:
        """Create a :class:`RewardSession` for the provided account."""

        if not account.email or not account.password:
            raise ValueError("Account credentials must be present")
        self._logger.info("Authenticating account", email=account.masked_email(), arguments=list(arguments or []))
        token = uuid4().hex
        session = RewardSession(
            profile_id=account.profile_id,
            email=account.email,
            token=token,
            created_at=datetime.utcnow(),
        )
        self._logger.success("Authentication finished", profile=account.profile_id)
        return session


__all__ = ["RewardLoginService"]
