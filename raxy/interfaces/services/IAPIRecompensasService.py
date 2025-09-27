"""Contrato para execução de tarefas no Rewards via API de alto nível."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping

from flask import Blueprint


class IAPIRecompensasService(ABC):
    """Expõe operações de alto nível sobre a API do Rewards."""

    @property
    @abstractmethod
    def blueprint(self) -> Blueprint:
        """Retorna o blueprint Flask que expõe os endpoints públicos."""

    @abstractmethod
    def executar_tarefas(
        self,
        dados: Mapping[str, object],
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, int]:
        """Executa tarefas com base no JSON retornado pela API."""
