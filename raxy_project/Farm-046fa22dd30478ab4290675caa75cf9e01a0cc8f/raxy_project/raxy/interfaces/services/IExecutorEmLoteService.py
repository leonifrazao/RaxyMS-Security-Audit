"""Contrato para execução de fluxos em lote."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Sequence, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.domain import Conta



class IExecutorEmLoteService(ABC):
    """Executa fluxos de automação para múltiplas contas."""

    @abstractmethod
    def executar(self, acoes: Iterable[str] | None = None, contas: Sequence["Conta"] | None = None) -> None:
        """Processa as contas informadas ou, se ausentes, as cadastradas no repositório."""
