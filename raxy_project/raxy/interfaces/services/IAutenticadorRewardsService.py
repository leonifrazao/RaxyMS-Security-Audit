"""Contrato para autenticação no Microsoft Rewards."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.domain import Conta
    from raxy.core.session_service import SessaoSolicitacoes


class IAutenticadorRewardsService(ABC):
    """Orquestra o processo de login no Rewards."""

    @abstractmethod
    def validar_credenciais(self, email: str, senha: str) -> tuple[str, str]:
        """Normaliza e valida email/senha antes do login."""

    @abstractmethod
    def executar(self, conta: "Conta", proxy: str) -> "SessaoSolicitacoes":
        """Realiza o login e retorna a sessão autenticada."""
