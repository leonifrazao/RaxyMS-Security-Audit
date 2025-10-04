# raxy/services/executor_service.py

"""Serviço que orquestra ações em múltiplas contas de forma concorrente."""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from raxy.config import DEFAULT_ACTIONS, DEFAULT_MAX_WORKERS, DEFAULT_USERS_FILE
from raxy.domain import Conta
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import (
    IAutenticadorRewardsService,
    IExecutorEmLoteService,
    ILoggingService,
    IPerfilService,
    IRewardsDataService,
    IProxyService,
    IBingSuggestion
)


@dataclass(slots=True)
class ExecutorConfig:
    """Configuração utilizada pelo executor em lote."""
    users_file: str = DEFAULT_USERS_FILE
    actions: list[str] = field(default_factory=lambda: list(DEFAULT_ACTIONS))
    max_workers: int = DEFAULT_MAX_WORKERS
    api_error_words: list[str] = field(default_factory=list)

    @classmethod
    def from_users_file(cls, caminho: str) -> "ExecutorConfig":
        cfg = cls()
        cfg.users_file = caminho
        return cfg


class ExecutorEmLote(IExecutorEmLoteService):
    """Executa os fluxos selecionados para cada conta em paralelo."""

    def __init__(
        self,
        *,
        bing_search: IBingSuggestion,
        conta_repository: IContaRepository,
        proxy_service: IProxyService,
        autenticador: IAutenticadorRewardsService,
        perfil_service: IPerfilService,
        rewards_data: IRewardsDataService,
        logger: ILoggingService,
        db_repository: IDatabaseRepository, # Recebe a nova dependência
        config: ExecutorConfig | None = None,
    ) -> None:
        self._config = config or ExecutorConfig()
        self._proxy_service = proxy_service
        self._logger = logger
        self._autenticador = autenticador
        self._perfil_service = perfil_service
        self._conta_repository = conta_repository
        self._rewards_data = rewards_data
        self._bing_search = bing_search
        self._db_repository = db_repository # Armazena a dependência

    def executar(self, acoes: Iterable[str] | None = None, contas: Sequence[Conta] | None = None) -> None:
        """
        Orquestra a execução concorrente do processamento de contas.
        """
        acoes_normalizadas = self._normalizar_acoes(acoes or self._config.actions)
        contas_processar = list(contas) if contas is not None else self._conta_repository.listar()

        if not contas_processar:
            self._logger.aviso("Nenhuma conta encontrada para processar.")
            return

        total_contas = len(contas_processar)
        self._proxy_service.start(threads=200, amounts=total_contas, auto_test=True)

        self._logger.info(
            "Iniciando processamento em lote com multithreading.",
            total_contas=total_contas,
            max_workers=self._config.max_workers
        )

        proxies = self._proxy_service.get_http_proxy()
        if len(proxies) < total_contas:
            self._logger.aviso(
                "Número de proxys inferior ao total de contas. Algumas contas não serão processadas.",
                proxys_disponiveis=len(proxies),
                contas=total_contas
            )

        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            futuros = {
                executor.submit(self._processar_conta, conta, acoes_normalizadas, proxy)
                for conta, proxy in zip(contas_processar, proxies)
            }

            for futuro in as_completed(futuros):
                try:
                    futuro.result()
                except Exception as exc:
                    self._logger.erro(
                        "Uma thread de processamento encontrou um erro inesperado e foi encerrada.",
                        erro=str(exc)
                    )

        self._logger.sucesso("Processamento em lote finalizado para todas as contas.")

    def _processar_conta(self, conta: Conta, acoes: Sequence[str], proxy: dict) -> None:
        """
        Este método é executado por cada thread de forma isolada para processar uma única conta.
        """
        scoped_logger = self._logger.com_contexto(conta=conta.email)
        scoped_logger.info("Thread iniciada para processamento da conta.")

        try:
            self._perfil_service.garantir_perfil(conta.id_perfil, conta.email, conta.senha)
            
            sessao = self._autenticador.executar(conta, proxy=proxy) if "login" in acoes else None
            
            pontos_iniciais = self._rewards_data.obter_pontos(sessao.base_request)
            pontos_finais = 0

            if sessao:
                if "rewards" in acoes:
                    self._rewards_data.pegar_recompensas(sessao.base_request)
                    pontos_finais = self._rewards_data.obter_pontos(sessao.base_request)
                    if pontos_finais > pontos_iniciais:
                        scoped_logger.info("Pontos atuais", pontos=pontos_finais)
                    else:
                        scoped_logger.aviso("Nenhum ponto adicional foi ganho após pegar recompensas.", pontos=pontos_finais)

                if "solicitacoes" in acoes:
                    sugestoes = self._bing_search.get_all(sessao.base_request, "Brasil")
                    scoped_logger.info("Sugestões de busca encontradas", total=len(sugestoes))
            
                # AO FINAL DE TODO O PROCESSO, ADICIONA AS INFORMAÇÕES NO BANCO
                if pontos_finais > 0:
                    self._db_repository.adicionar_registro_farm(
                        email=conta.email,
                        pontos=pontos_finais
                    )
                else:
                    scoped_logger.aviso("Pontuação final não foi determinada, registro no banco de dados ignorado.")

            scoped_logger.sucesso("Conta processada com sucesso pela thread.")

        except Exception as exc:
            scoped_logger.erro("Falha ao processar conta na thread.", erro=str(exc))
            raise

    @staticmethod
    def _normalizar_acoes(acoes: Iterable[str]) -> list[str]:
        """Limpa e padroniza a lista de ações a serem executadas."""
        return [acao.strip().lower() for acao in acoes if acao and acao.strip()]

__all__ = ["ExecutorEmLote", "ExecutorConfig"]