"""Contrato para operações de API HTTP do Microsoft Rewards sobre SessionManagerService."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.core.session_manager_service import SessionManagerService


class IRewardsDataService(ABC):
    """Opera sobre a API HTTP do Rewards usando o SessionManagerService."""

    @abstractmethod
    def obter_pontos(self, sessao: "SessionManagerService", *, bypass_request_token: bool = False) -> int:
        """Retorna o total de pontos disponíveis."""

    @abstractmethod
    def obter_recompensas(
        self,
        sessao: "SessionManagerService",
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, object]:
        """Recupera os conjuntos de promoções e informações crus da API."""

    @abstractmethod
    def pegar_recompensas(
        self,
        sessao: "SessionManagerService",
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, object]:
        """Tenta executar promoções disponíveis e retorna o resumo da execução."""
