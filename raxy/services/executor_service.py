"""Servico responsavel por orquestrar acoes em multiplas contas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from api.rewards_api import APIRecompensas
from config import (
    DEFAULT_ACTIONS,
    DEFAULT_API_ERROR_WORDS,
    DEFAULT_MAX_WORKERS,
    DEFAULT_USERS_FILE,
)
from domain import Conta
from interfaces.services import (
    IAutenticadorRewardsService,
    IExecutorEmLoteService,
    IGerenciadorSolicitacoesService,
    ILoggingService,
    IPerfilService,
    IProxyService,
    IRewardsAPIsService,
    IRewardsDataService,
)
from interfaces.repositories import IContaRepository
from services.api_execution_service import BuscaPayloadConfig, RewardsAPIsService
from services.session_service import BaseRequest
from services.solicitacoes_service import GerenciadorSolicitacoesRewards


def _missing_base_request() -> BaseRequest:
    raise LookupError("BaseRequest nao configurado")


_BUSCA_PAYLOADS_PADRAO: tuple[BuscaPayloadConfig, ...] = (
    BuscaPayloadConfig(nome="desktop", quantidade=5),
    BuscaPayloadConfig(nome="mobile", quantidade=5),
)


@dataclass(slots=True)
class ExecutorConfig:
    """Configuracao utilizada pelo executor em lote."""

    users_file: str = DEFAULT_USERS_FILE
    actions: list[str] = field(default_factory=lambda: list(DEFAULT_ACTIONS))
    max_workers: int = DEFAULT_MAX_WORKERS
    api_error_words: list[str] = field(default_factory=lambda: list(DEFAULT_API_ERROR_WORDS))

    @classmethod
    def from_users_file(cls, caminho: str) -> "ExecutorConfig":
        cfg = cls()
        cfg.users_file = caminho
        return cfg


class ExecutorEmLote(IExecutorEmLoteService):
    """Executa os fluxos selecionados para cada conta cadastrada."""

    def __init__(
        self,
        *,
        conta_repository: IContaRepository,
        proxy_service: IProxyService,
        autenticador: IAutenticadorRewardsService,
        perfil_service: IPerfilService,
        rewards_data: IRewardsDataService,
        logger: ILoggingService,
        config: ExecutorConfig | None = None,
        api_factory: Callable[[IGerenciadorSolicitacoesService], APIRecompensas] | None = None,
        rewards_api_service_factory: Callable[[Callable[[], BaseRequest], IGerenciadorSolicitacoesService, ILoggingService], IRewardsAPIsService] | None = None,
    ) -> None:
        self._config = config or ExecutorConfig()
        self._proxy_service = proxy_service
        self._logger = logger
        self._autenticador = autenticador
        self._perfil_service = perfil_service
        self._conta_repository = conta_repository
        self._rewards_data = rewards_data
        self._api_factory = api_factory or (lambda ger: APIRecompensas(ger))
        self._rewards_api_service_factory = rewards_api_service_factory or (
            lambda provider, gerenciador, scoped_logger: RewardsAPIsService(
                request_provider=provider,
                gerenciador=gerenciador,
                rewards_data=self._rewards_data,
                api_recompensas_factory=self._api_factory,
                logger=scoped_logger,
            )
        )

    def executar(self, acoes: Iterable[str] | None = None) -> None:
        acoes_normalizadas = self._normalizar_acoes(acoes or self._config.actions)
        contas = self._conta_repository.listar()
        self._proxy_service.test(threads=5)
        self._proxy_service.start(amounts=len(contas), country='US')

        for conta, proxy in zip(contas, self._proxy_service.get_http_proxy()):
            self._processar_conta(conta, acoes_normalizadas, proxy=proxy)

    def _processar_conta(self, conta: Conta, acoes: Sequence[str], proxy: str) -> None:
        scoped = self._logger.com_contexto(conta=conta.email)
        scoped.info("Iniciando processamento da conta")
        scoped.info(proxy)

        try:
            self._perfil_service.garantir_perfil(conta.id_perfil, conta.email, conta.senha)
            sessao = self._autenticador.executar(conta, proxy=proxy) if "login" in acoes else None

            if sessao:
                def provider() -> BaseRequest:
                    return sessao.base_request

                executar_recompensas = "rewards" in acoes
                executar_solicitacoes = "solicitacoes" in acoes

                api_service: IRewardsAPIsService | None = None
                if executar_recompensas or executar_solicitacoes:
                    gerenciador = GerenciadorSolicitacoesRewards(
                        sessao,
                        palavras_erro=tuple(self._config.api_error_words),
                    )
                    api_service = self._rewards_api_service_factory(provider, gerenciador, scoped)

                self._rewards_data.set_request_provider(provider)
                try:
                    if executar_recompensas and api_service:
                        try:
                            pontos = api_service.obter_pontos(bypass_request_token=True)
                            scoped.info("Pontos disponiveis coletados", pontos=pontos)
                        except Exception as exc:  # pragma: no cover - logging auxiliar
                            scoped.aviso("Falhou ao obter pontos", erro=str(exc))

                        try:
                            dados_recompensas = api_service.obter_recompensas(bypass_request_token=True)
                        except Exception as exc:  # pragma: no cover - logging auxiliar
                            scoped.aviso("Falhou ao obter recompensas", erro=str(exc))
                            dados_recompensas = {}

                        resumo_execucao = api_service.executar_promocoes(
                            dados_recompensas,
                            bypass_request_token=True,
                        )
                        scoped.info(
                            "Execucao de promocoes finalizada",
                            executadas=resumo_execucao.get("executadas"),
                            ignoradas=resumo_execucao.get("ignoradas"),
                        )

                    if executar_solicitacoes and api_service:
                        try:
                            resultados = api_service.executar_pesquisas(_BUSCA_PAYLOADS_PADRAO)
                            contagem: dict[str, int] = {}
                            for resultado in resultados:
                                contagem[resultado.payload] = contagem.get(resultado.payload, 0) + 1
                            scoped.info(
                                "Pesquisas Bing executadas",
                                total=len(resultados),
                                payloads=contagem,
                            )
                        except Exception as exc:  # pragma: no cover - logging auxiliar
                            scoped.aviso("Falhou ao executar pesquisas Bing", erro=str(exc))
                finally:
                    self._rewards_data.set_request_provider(_missing_base_request)

            scoped.sucesso("Conta processada com sucesso")
        except Exception as exc:  # pragma: no cover - fluxo de log
            scoped.erro("Falha ao processar conta", erro=str(exc))

    @staticmethod
    def _normalizar_acoes(acoes: Iterable[str]) -> list[str]:
        return [acao.strip().lower() for acao in acoes if acao and acao.strip()]


__all__ = ["ExecutorEmLote", "ExecutorConfig"]
