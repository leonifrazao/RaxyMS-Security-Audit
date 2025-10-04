"""Contrato para armazenar histórico de pontuação das contas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.domain import Conta


class IHistoricoPontuacaoRepository(ABC):
    """Contrato para armazenar histórico de pontuação das contas."""

    @abstractmethod
    def registrar_pontos(self, conta: "Conta", pontos: int) -> None:
        """Associa o total de pontos mais recente à conta."""

    @abstractmethod
    def obter_ultimo_total(self, conta: "Conta") -> int | None:
        """Recupera o último total de pontos conhecido para a conta."""
