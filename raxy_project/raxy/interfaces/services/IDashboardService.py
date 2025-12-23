"""Interface para serviços de dashboard em tempo real."""

from __future__ import annotations

from abc import ABC, abstractmethod


class IDashboardService(ABC):
    """Define a interface esperada de um serviço de dashboard."""

    @abstractmethod
    def start(self, total_accounts: int) -> None:
        """Inicia o dashboard com o total de contas a processar."""

    @abstractmethod
    def stop(self) -> None:
        """Para o dashboard."""

    @abstractmethod
    def update_worker(self, worker_id: str, email: str, status: str) -> None:
        """Atualiza o status de um worker."""

    @abstractmethod
    def worker_done(self, worker_id: str) -> None:
        """Remove worker da tabela ativa."""

    @abstractmethod
    def increment_success(self) -> None:
        """Incrementa contador de sucesso."""

    @abstractmethod
    def increment_failure(self) -> None:
        """Incrementa contador de falha."""

    @abstractmethod
    def set_global_status(self, status: str) -> None:
        """Define status global da aplicação."""

    @abstractmethod
    def update(self) -> None:
        """Força atualização da renderização."""
