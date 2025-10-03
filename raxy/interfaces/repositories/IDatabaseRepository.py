"""Contrato para persistência de dados em um banco de dados genérico."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

class IDatabaseRepository(ABC):
    """Define as operações necessárias para interagir com o banco de dados da farm."""

    @abstractmethod
    def adicionar_registro_farm(self, email: str, pontos: int) -> Mapping[str, Any] | None:
        """
        Adiciona ou atualiza o registro de uma conta após o processo de farm.

        Args:
            email: O email da conta processada.
            pontos: A pontuação atual da conta.

        Returns:
            O registro inserido/atualizado ou None em caso de falha.
        """
        raise NotImplementedError

    @abstractmethod
    def consultar_conta(self, email: str) -> Mapping[str, Any] | None:
        """
        Consulta os dados de uma conta específica pelo email.

        Args:
            email: O email da conta a ser consultada.

        Returns:
            Os dados da conta ou None se não for encontrada.
        """
        raise NotImplementedError