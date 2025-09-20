"""Convenience helpers for reading environment variables."""

from __future__ import annotations

import os
from typing import Iterable, List, Optional


class EnvironmentReader:
    """Minimal access layer to parse environment variables safely."""

    @staticmethod
    def as_bool(key: str, *, default: Optional[bool] = None) -> Optional[bool]:
        """Return a boolean value if the variable is set."""

        value = os.getenv(key)
        if value is None:
            return default
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default

    @staticmethod
    def as_int(key: str) -> Optional[int]:
        """Return an integer if conversion is possible."""

        value = os.getenv(key)
        if value is None:
            return None
        try:
            return int(value.strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def as_list(key: str, *, separator: str = ",", default: Optional[Iterable[str]] = None) -> List[str]:
        """Split comma separated values removing blanks."""

        value = os.getenv(key)
        items = default if value is None else value.split(separator)
        result: List[str] = []
        for item in items or []:
            cleaned = str(item).strip().lower()
            if cleaned:
                result.append(cleaned)
        return result


__all__ = ["EnvironmentReader"]
