"""Contrato para operações de API HTTP do Microsoft Rewards."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Mapping, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.services.session_service import BaseRequest


class IBingSuggestion(ABC):
    """Opera sobre a API HTTP do Rewards sem interação com navegador."""


    @abstractmethod
    def get_all(self, keyword: str):
        """
        Busca todas as sugestões de pesquisa para uma determinada palavra-chave.

        Args:
            keyword: O termo a ser pesquisado.

        Returns:
            Uma lista de dicionários, onde cada um representa uma sugestão.
        
        Raises:
            ValueError: Se a palavra-chave for inválida.
            TypeError: Se a resposta da API não tiver o formato esperado.
        """

    @abstractmethod
    def get_random(self, keyword: str):
        """
        Busca uma sugestão de pesquisa aleatória para a palavra-chave.

        Args:
            keyword: O termo a ser pesquisado.

        Returns:
            Um dicionário representando uma única sugestão aleatória.

        Raises:
            ValueError: Se nenhuma sugestão for encontrada.
        """