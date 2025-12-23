"""Contrato para sugestões de pesquisa do Bing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.interfaces.services import ISessionManager


class IBingSuggestion(ABC):
    @abstractmethod
    def get_all(
        self, 
        sessao: "ISessionManager", 
        query: str, 
        *, 
        country: str | None = None
    ) -> list[Any]:
        """Retorna todas as sugestões para a palavra-chave."""

    @abstractmethod
    def get_random(
        self, 
        sessao: "ISessionManager", 
        keyword: str, 
        *, 
        country: str | None = None
    ) -> Any | None:
        """Retorna uma sugestão aleatória para a palavra-chave."""

    @abstractmethod
    def realizar_pesquisa(
        self, 
        sessao: "ISessionManager", 
        query: str,
        **kwargs
    ) -> bool:
        """Realiza uma pesquisa no Bing para pontuar."""
