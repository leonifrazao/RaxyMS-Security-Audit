"""Contrato para execução de tarefas no Rewards via API de alto nível."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping


class IAPIRecompensasService(ABC):
    """Expõe operações de alto nível sobre a API do Rewards."""

    @abstractmethod
    def executar_tarefas(
        self,
        dados: Mapping[str, object],
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, int]:
        """Executa tarefas com base no JSON retornado pela API."""
