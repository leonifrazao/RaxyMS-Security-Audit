"""Contrato para operações de API HTTP do Microsoft Rewards."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Mapping, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.services.session_service import BaseRequest


class IRewardsDataService(ABC):
    """Opera sobre a API HTTP do Rewards sem interação com navegador."""

    @abstractmethod
    def obter_pontos(self, base: "BaseRequest", *, bypass_request_token: bool = False) -> int:
        """Retorna o total de pontos disponíveis."""

    @abstractmethod
    def obter_recompensas(
        self,
        base: "BaseRequest",
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, object]:
        """Recupera os conjuntos de promoções e informações crus da API."""

    @abstractmethod
    def pegar_recompensas(
        self,
        base: "BaseRequest",
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, object]:
        """Tenta executar promoções disponíveis e retorna o resumo da execução."""
