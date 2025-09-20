"""Session data produced after a successful login."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class RewardSession:
    """Hold the lightweight authentication state for the rewards API."""

    profile_id: str
    email: str
    token: str
    created_at: datetime


__all__ = ["RewardSession"]
