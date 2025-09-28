"""Contrato para execucao coordenada das APIs de Rewards e Bing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, Sequence, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.services.api_execution_service import BuscaPayloadConfig, ResultadoBusca
    from raxy.services.session_service import BaseRequest


class IRewardsAPIsService(ABC):
    """Define operacoes de alto nivel sobre as APIs de Rewards e Bing."""

    @abstractmethod
    def executar_pesquisas(
        self,
        payloads: Sequence["BuscaPayloadConfig"] | None = None,
        *,
        base: "BaseRequest" | None = None,
    ) -> list["ResultadoBusca"]:
        """Executa consultas no Bing retornando o resumo de cada request."""

    @abstractmethod
    def obter_pontos(
        self,
        *,
        bypass_request_token: bool = False,
        base: "BaseRequest" | None = None,
    ) -> int:
        """Obtem o total de pontos disponiveis para a sessao atual."""

    @abstractmethod
    def obter_recompensas(
        self,
        *,
        bypass_request_token: bool = False,
        base: "BaseRequest" | None = None,
    ) -> Mapping[str, object]:
        """Recupera o JSON bruto de promocoes a partir do Rewards."""

    @abstractmethod
    def executar_promocoes(
        self,
        dados: Mapping[str, object] | None = None,
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, int]:
        """Aciona as promocoes pendentes retornando o resumo de execucao."""


__all__ = ["IRewardsAPIsService"]
