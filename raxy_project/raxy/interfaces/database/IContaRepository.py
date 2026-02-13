"""Contrato para persistência de contas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Sequence, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.models import Conta


class IContaRepository(ABC):
    """Define as operações necessárias para gerenciar contas."""

    @abstractmethod
    def listar(self) -> list["Conta"]:
        """Recupera todas as contas cadastradas."""

    @abstractmethod
    def salvar(self, conta: "Conta") -> "Conta":
        """Persiste ou atualiza uma conta."""

    @abstractmethod
    def salvar_varias(self, contas: Iterable["Conta"]) -> Sequence["Conta"]:
        """Persiste um conjunto de contas de uma vez."""

    @abstractmethod
    def remover(self, conta: "Conta") -> None:
        """Remove a conta informada."""
