# raxy/interfaces/services/IBingFlyoutService.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from raxy.interfaces.services import ISessionManager
    from raxy.models.flyout import FlyoutResult


class IBingFlyoutService(ABC):
    @abstractmethod
    def executar(self, sessao: "ISessionManager") -> Optional["FlyoutResult"]:
        """Executa o fluxo de onboarding do flyout usando a sessão autenticada."""
