# raxy_project/raxy/interfaces/services/IBingFlyoutService.py

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from botasaurus.browser import Driver

if TYPE_CHECKING:
    from raxy.core.session_service import SessaoSolicitacoes

class IBingFlyoutService(ABC):
    """
    Define a interface para serviços que interagem com o painel flyout do Bing Rewards,
    especialmente para ações de onboarding como definir metas.
    """
    
    def abrir_flyout(self, *, profile: str, proxy: dict) -> None:
        """Abre o painel flyout de onboarding utilizando o perfil informado."""
        raise NotImplementedError