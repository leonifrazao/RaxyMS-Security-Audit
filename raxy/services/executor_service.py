"""Serviço responsável por orquestrar ações em múltiplas contas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

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
    ILoggingService,
    IPerfilService,
    IRewardsDataService,
    IProxyService,
)
from interfaces.repositories import IContaRepository
from services.session_service import BaseRequest


def _missing_base_request() -> BaseRequest:
    raise LookupError("BaseRequest não configurado")


@dataclass(slots=True)
class ExecutorConfig:
    """Configuração utilizada pelo executor em lote."""

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
    ) -> None:
        self._config = config or ExecutorConfig()
        self._proxy_service = proxy_service
        self._logger = logger
        self._autenticador = autenticador
        self._perfil_service = perfil_service
        self._conta_repository = conta_repository
        self._rewards_data = rewards_data

    def executar(self, acoes: Iterable[str] | None = None) -> None:
        acoes_normalizadas = self._normalizar_acoes(acoes or self._config.actions)
        contas = self._conta_repository.listar()
        self._proxy_service.start(threads=5, amounts=len(contas), auto_test=True)
        # input("Pressione Enter após iniciar o servidor de API de proxies...")
        # self._proxy_service.test(threads=5)

        for conta, proxy in zip(contas, self._proxy_service.get_http_proxy()):
            # conta.proxy = proxy
            self._processar_conta(conta, acoes_normalizadas, proxy=proxy)

    def _processar_conta(self, conta: Conta, acoes: Sequence[str], proxy) -> None:
        scoped = self._logger.com_contexto(conta=conta.email)
        scoped.info("Iniciando processamento da conta")
        scoped.info(mensagem="Proxy atual: ", uri=proxy["uri"])

        try:
            self._perfil_service.garantir_perfil(conta.id_perfil, conta.email, conta.senha)
            sessao = self._autenticador.executar(conta, proxy=proxy) if "login" in acoes else None

            if sessao:

                self._rewards_data.set_request_provider(lambda base=sessao.base_request: base)
                try:
                    if "rewards" in acoes:
                        try:
                            pontos = self._rewards_data.obter_pontos(sessao.base_request, bypass_request_token=True)
                            scoped.info("Pontos disponíveis coletados", pontos=pontos)
                        except Exception as exc:  # pragma: no cover - logging auxiliar
                            scoped.aviso("Falhou ao obter pontos", erro=str(exc))

                        try:
                            self._rewards_data.pegar_recompensas(
                                sessao.base_request,
                                bypass_request_token=True,
                            )
                        except Exception as exc:  # pragma: no cover - logging auxiliar
                            scoped.aviso("Falhou ao obter recompensas", erro=str(exc))
                            

                        # resumo_execucao = api.executar_tarefas(dados_recompensas)
                        # scoped.info(
                        #     "Execução de promoções finalizada",
                        #     executadas=resumo_execucao.get("executadas"),
                        #     ignoradas=resumo_execucao.get("ignoradas"),
                        # )
                finally:
                    self._rewards_data.set_request_provider(_missing_base_request)

            scoped.sucesso("Conta processada com sucesso")
        except Exception as exc:  # pragma: no cover - fluxo de log
            scoped.erro("Falha ao processar conta", erro=str(exc))

    @staticmethod
    def _normalizar_acoes(acoes: Iterable[str]) -> list[str]:
        return [acao.strip().lower() for acao in acoes if acao and acao.strip()]


__all__ = ["ExecutorEmLote", "ExecutorConfig"]
