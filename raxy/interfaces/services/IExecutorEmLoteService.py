"""Contrato para execução de fluxos em lote."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable


class IExecutorEmLoteService(ABC):
    """Executa fluxos de automação para múltiplas contas."""

    @abstractmethod
    def executar(self, acoes: Iterable[str] | None = None) -> None:
        """Processa as contas configuradas seguindo as ações informadas."""
