"""Lightweight structured logger with contextual support."""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping


class StructuredLogger:
    """Thin wrapper above :mod:`logging` focused on context-rich messages."""

    SUCCESS_LEVEL = 25

    def __init__(self, name: str = "raxy", *, context: Mapping[str, Any] | None = None) -> None:
        logging.addLevelName(self.SUCCESS_LEVEL, "SUCCESS")
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)
        self._context: Dict[str, Any] = dict(context or {})

    def bind(self, **context: Any) -> "StructuredLogger":
        """Return a new logger that always includes the provided context."""

        merged = {**self._context}
        merged.update({k: v for k, v in context.items() if v is not None})
        return StructuredLogger(self._logger.name, context=merged)

    def debug(self, message: str, **extra: Any) -> None:
        self._log(logging.DEBUG, message, extra)

    def info(self, message: str, **extra: Any) -> None:
        self._log(logging.INFO, message, extra)

    def success(self, message: str, **extra: Any) -> None:
        self._log(self.SUCCESS_LEVEL, message, extra)

    def warning(self, message: str, **extra: Any) -> None:
        self._log(logging.WARNING, message, extra)

    def error(self, message: str, **extra: Any) -> None:
        self._log(logging.ERROR, message, extra)

    def _log(self, level: int, message: str, extra: Mapping[str, Any]) -> None:
        """Compose the final log message and delegate to the wrapped logger."""

        payload = {**self._context}
        payload.update({k: v for k, v in extra.items() if v is not None})
        suffix = " ".join(f"{key}={value}" for key, value in payload.items())
        text = f"{message} | {suffix}" if suffix else message
        self._logger.log(level, text)


__all__ = ["StructuredLogger"]
