"""Contrato para sugestões de pesquisa do Bing usando SessionManagerService."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.core.session_manager_service import SessionManagerService


class IBingSuggestion(ABC):
    @abstractmethod
    def get_all(self, sessao: "SessionManagerService", keyword: str) -> list[dict[str, Any]]:
        """Retorna todas as sugestões para a palavra-chave."""

    @abstractmethod
    def get_random(self, sessao: "SessionManagerService", keyword: str) -> dict[str, Any]:
        """Retorna uma sugestão aleatória para a palavra-chave."""
