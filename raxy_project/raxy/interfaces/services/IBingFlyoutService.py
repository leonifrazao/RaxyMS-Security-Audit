# raxy_project/raxy/interfaces/services/IBingFlyoutService.py

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raxy.core.session_service import SessaoSolicitacoes

class IBingFlyoutService(ABC):
    """
    Define a interface para serviços que interagem com o painel flyout do Bing Rewards,
    especialmente para ações de onboarding como definir metas.
    """

    @abstractmethod
    def set_goal(self, sessao: SessaoSolicitacoes, sku: str) -> bool:
        """
        Executa o fluxo completo para definir uma meta de resgate e coletar os pontos de bônus.

        Args:
            sessao: A sessão autenticada do usuário.
            sku: O SKU do item de catálogo a ser definido como meta.

        Returns:
            True se a operação for bem-sucedida, False caso contrário.
        """
        raise NotImplementedError