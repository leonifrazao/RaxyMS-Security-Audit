"""Contrato para gerenciamento de solicitações manualmente configuradas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.services.session_service import ParametrosManualSolicitacao


class IGerenciadorSolicitacoesService(ABC):
    """Mantém o estado e parâmetros para chamadas manuais de API."""

    @abstractmethod
    def parametros_manuais(self, *, interativo: bool | None = None) -> "ParametrosManualSolicitacao":
        """Retorna os parâmetros atuais para uma requisição manual."""

    @property
    @abstractmethod
    def dados_sessao(self) -> object | None:
        """Retorna dados complementares da sessão (ex.: tokens)."""
