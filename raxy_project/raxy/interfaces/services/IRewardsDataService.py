"""Contrato para operações de API HTTP do Microsoft Rewards."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, TYPE_CHECKING, Any, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from raxy.interfaces.services import ISessionManager
    from raxy.models.rewards import RewardsDashboard, CollectionResult


class IRewardsDataService(ABC):
    """Opera sobre a API HTTP do Rewards usando sessões gerenciadas."""

    @abstractmethod
    def obter_pontos(self, sessao: "ISessionManager", *, bypass_request_token: bool = True) -> int:
        """Retorna o total de pontos disponíveis."""

    @abstractmethod
    def obter_recompensas(
        self,
        sessao: "ISessionManager",
        *,
        bypass_request_token: bool = True,
    ) -> "RewardsDashboard":
        """Recupera o dashboard completo de promoções."""

    @abstractmethod
    def pegar_recompensas(
        self,
        sessao: "ISessionManager",
        *,
        bypass_request_token: bool = True,
    ) -> "CollectionResult":
        """Tenta executar promoções disponíveis e retorna o resumo da execução."""

    @abstractmethod
    def get_user_level(self, dashboard: "RewardsDashboard") -> str:
        """Retorna o nome do nível atual do usuário (ex: 'Level 2')."""

    @abstractmethod
    def get_pc_search_progress(self, dashboard: "RewardsDashboard") -> Tuple[int, int]:
        """
        Retorna o progresso de pontos de busca no PC.
        Returns: (pontos_atuais, maximo_pontos)
        """

    @abstractmethod
    def get_mobile_search_progress(self, dashboard: "RewardsDashboard") -> Tuple[int, int]:
        """
        Retorna o progresso de pontos de busca Mobile.
        Returns: (pontos_atuais, maximo_pontos)
        """
