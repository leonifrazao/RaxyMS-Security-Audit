# raxy/interfaces/services/IBingFlyoutService.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raxy.interfaces.services import ISessionManager


class IBingFlyoutService(ABC):
    @abstractmethod
    def executar(self, sessao: "ISessionManager") -> None:
        """Executa o fluxo de onboarding do flyout usando a sessão autenticada."""
