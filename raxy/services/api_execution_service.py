"""Servico utilitario para execucao coordenada das APIs em ``raxy.api``.

Este modulo encapsula o uso das classes ``BingSearchAPI``, ``APIRecompensas``
e ``RewardsDataAPI`` para facilitar fluxos programaticos (sem expor endpoints
HTTP). Ele provem uma camada coesa que diferencia os payloads esperados por
cada API, cuidando de detalhes como atualizacao dos parametros de pesquisa
(``q``/``pq``) e reaproveitamento de sessoes autenticadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from api.bing_search_api import BingSearchAPI
from interfaces.services import (
    IAPIRecompensasService,
    IGerenciadorSolicitacoesService,
    ILoggingService,
    IRewardsAPIsService,
    IRewardsDataService,
)
from services.session_service import BaseRequest


@dataclass(slots=True)
class BuscaPayloadConfig:
    """Configuracao de um conjunto de buscas a serem executadas."""

    nome: str
    quantidade: int = 1
    consultas: Sequence[str] | None = None


@dataclass(slots=True)
class ResultadoBusca:
    """Registro com o resumo de uma busca realizada."""

    payload: str
    resultado: Mapping[str, object]


class RewardsAPIsService(IRewardsAPIsService):
    """Executa chamadas coordenadas as APIs de Rewards e Bing."""

    def __init__(
        self,
        *,
        request_provider: Callable[[], BaseRequest],
        gerenciador: IGerenciadorSolicitacoesService,
        rewards_data: IRewardsDataService,
        api_recompensas_factory: Callable[[IGerenciadorSolicitacoesService], IAPIRecompensasService],
        bing_api_factory: Callable[[Callable[[], BaseRequest]], BingSearchAPI] | None = None,
        logger: ILoggingService | None = None,
    ) -> None:
        if request_provider is None:
            raise ValueError("request_provider e obrigatorio")
        if gerenciador is None:
            raise ValueError("gerenciador e obrigatorio")
        if rewards_data is None:
            raise ValueError("rewards_data e obrigatorio")
        if api_recompensas_factory is None:
            raise ValueError("api_recompensas_factory e obrigatorio")

        self._request_provider = request_provider
        self._gerenciador = gerenciador
        self._rewards_data = rewards_data
        self._api_recompensas = api_recompensas_factory(gerenciador)
        self._logger = logger

        fabrica_bing = bing_api_factory or (lambda provider: BingSearchAPI(request_provider=provider))
        self._bing_api = fabrica_bing(request_provider)

    # ------------------------------------------------------------------
    # Bing Search API
    # ------------------------------------------------------------------
    def executar_pesquisas(
        self,
        payloads: Sequence[BuscaPayloadConfig] | None = None,
        *,
        base: BaseRequest | None = None,
    ) -> list[ResultadoBusca]:
        """Executa buscas do Bing respeitando a configuracao de payloads.

        Args:
            payloads: Sequencia de configuracoes. Cada payload pode definir uma
                lista fixa de consultas (``consultas``) ou apenas a quantidade
                desejada. Quando nao ha consultas explicitas, o gerador interno
                do ``BingSearchAPI`` propoe buscas tematicamente variadas.
            base: ``BaseRequest`` ja autenticada. Caso nao seja fornecida, o
                provider configurado no servico sera utilizado.

        Returns:
            Lista de ``ResultadoBusca`` com um registro por consulta executada.
        """

        base_request = base or self._request_provider()
        definicoes = list(payloads) if payloads else [BuscaPayloadConfig(nome="default", quantidade=1)]

        resultados: list[ResultadoBusca] = []
        for config in definicoes:
            total_execucoes = config.quantidade if config.quantidade and config.quantidade > 0 else 0
            consultas = list(config.consultas or [])

            if not consultas and total_execucoes:
                consultas = [None] * total_execucoes
            elif total_execucoes and len(consultas) < total_execucoes:
                consultas.extend([None] * (total_execucoes - len(consultas)))

            for consulta in consultas[:total_execucoes]:
                resultado = self._bing_api.pesquisar(base=base_request, query=consulta)
                if isinstance(resultado, Mapping):
                    registros = dict(resultado)
                else:
                    registros = {"raw": resultado}
                resultados.append(ResultadoBusca(payload=config.nome, resultado=registros))
                if self._logger:
                    try:
                        self._logger.debug(
                            "Busca Bing executada",
                            payload=config.nome,
                            query=consulta or registros.get("query"),
                            url=registros.get("request", {}).get("url") if isinstance(registros.get("request"), Mapping) else None,
                        )
                    except Exception:
                        pass

        return resultados

    # ------------------------------------------------------------------
    # Rewards Data API
    # ------------------------------------------------------------------
    def obter_pontos(
        self,
        *,
        bypass_request_token: bool = False,
        base: BaseRequest | None = None,
    ) -> int:
        """Recupera o total de pontos disponiveis no Rewards."""

        base_request = base or self._request_provider()
        pontos = self._rewards_data.obter_pontos(base_request, bypass_request_token=bypass_request_token)
        if self._logger:
            try:
                self._logger.debug("Pontos coletados", pontos=pontos)
            except Exception:
                pass
        return pontos

    def obter_recompensas(
        self,
        *,
        bypass_request_token: bool = False,
        base: BaseRequest | None = None,
    ) -> Mapping[str, object]:
        """Retorna o JSON bruto de promocoes do Rewards."""

        base_request = base or self._request_provider()
        dados = self._rewards_data.obter_recompensas(base_request, bypass_request_token=bypass_request_token)
        if self._logger:
            try:
                self._logger.debug(
                    "Promocoes coletadas",
                    daily_sets=len(dados.get("daily_sets", [])) if isinstance(dados, Mapping) else None,
                    more_promotions=len(dados.get("more_promotions", [])) if isinstance(dados, Mapping) else None,
                )
            except Exception:
                pass
        return dados

    def executar_promocoes(
        self,
        dados: Mapping[str, object] | None = None,
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, int]:
        """Dispara a execucao de promocoes filtrando tarefas concluidas."""

        payload = dados if dados is not None else self.obter_recompensas(bypass_request_token=bypass_request_token)
        resumo = self._api_recompensas.executar_tarefas(payload, bypass_request_token=bypass_request_token)
        if self._logger:
            try:
                self._logger.debug(
                    "Promocoes executadas",
                    executadas=resumo.get("executadas"),
                    ignoradas=resumo.get("ignoradas"),
                )
            except Exception:
                pass
        return resumo


__all__ = ["RewardsAPIsService", "BuscaPayloadConfig", "ResultadoBusca"]
