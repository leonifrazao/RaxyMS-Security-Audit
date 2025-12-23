"""Contrato para execução de fluxos em lote."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Sequence, TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    from raxy.domain import Conta
    from raxy.domain.execution import BatchExecutionResult


class IExecutorEmLoteService(ABC):
    """Executa fluxos de automação para múltiplas contas."""

    @abstractmethod
    def executar(
        self, 
        acoes: Optional[Iterable[str]] = None, 
        contas: Optional[Sequence["Conta"]] = None
    ) -> "BatchExecutionResult":
        """Processa as contas informadas ou, se ausentes, as cadastradas no repositório."""
