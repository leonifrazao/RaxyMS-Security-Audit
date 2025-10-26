"""Contrato para operações de API HTTP do Microsoft Rewards."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.interfaces.services import ISessionManager


class IRewardsDataService(ABC):
    """Opera sobre a API HTTP do Rewards usando sessões gerenciadas."""

    @abstractmethod
    def obter_pontos(self, sessao: "ISessionManager", *, bypass_request_token: bool = False) -> int:
        """Retorna o total de pontos disponíveis."""

    @abstractmethod
    def obter_recompensas(
        self,
        sessao: "ISessionManager",
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, object]:
        """Recupera os conjuntos de promoções e informações crus da API."""

    @abstractmethod
    def pegar_recompensas(
        self,
        sessao: "ISessionManager",
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, object]:
        """Tenta executar promoções disponíveis e retorna o resumo da execução."""
