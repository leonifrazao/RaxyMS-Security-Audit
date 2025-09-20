"""Abstraction responsible for opening the rewards portal."""

from __future__ import annotations

from typing import Sequence

from ..logging.structured_logger import StructuredLogger


class RewardBrowser:
    """Simulate the navigation required to reach the rewards homepage."""

    def __init__(self, logger: StructuredLogger | None = None) -> None:
        self._logger = (logger or StructuredLogger()).bind(service="browser")

    def open_homepage(self, profile_id: str, *, arguments: Sequence[str] | None = None) -> None:
        """Record the intention to open the rewards dashboard."""

        items = [item for item in (arguments or []) if item]
        self._logger.info("Opening rewards homepage", profile=profile_id, arguments=items)


__all__ = ["RewardBrowser"]
