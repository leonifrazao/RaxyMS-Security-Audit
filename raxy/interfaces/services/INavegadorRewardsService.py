"""Contrato para interações de navegação no Rewards."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.services.session_service import SessaoSolicitacoes


class INavegadorRewardsService(ABC):
    """Encapsula interações de navegação no Rewards."""

    @abstractmethod
    def abrir_pagina(self, sessao: "SessaoSolicitacoes", destino: str | None = None) -> None:
        """Abre a página de Rewards no navegador controlado."""
