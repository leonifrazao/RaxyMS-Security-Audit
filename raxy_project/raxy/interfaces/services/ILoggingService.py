"""Contrato simplificado para serviços de logging."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any


class ILoggingService(ABC):
    """Define a interface esperada do logger de aplicação."""

    @abstractmethod
    def debug(self, mensagem: str, **dados: Any) -> None:
        """Registra mensagem de depuração."""

    @abstractmethod
    def info(self, mensagem: str, **dados: Any) -> None:
        """Registra mensagem informativa."""

    @abstractmethod
    def sucesso(self, mensagem: str, **dados: Any) -> None:
        """Registra mensagem de sucesso."""

    @abstractmethod
    def aviso(self, mensagem: str, **dados: Any) -> None:
        """Registra uma advertência."""

    @abstractmethod
    def erro(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro."""

    @abstractmethod
    def critico(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro crítico."""

    @abstractmethod
    def com_contexto(self, **dados: Any) -> "ILoggingService":
        """Retorna um logger derivado com contexto adicional."""

    @abstractmethod
    def etapa(self, titulo: str, **dados: Any) -> AbstractContextManager[None]:
        """Cria um contexto de execução para agrupar logs."""
