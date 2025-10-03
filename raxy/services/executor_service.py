# raxy/services/executor_service.py

"""Serviço que orquestra ações em múltiplas contas de forma concorrente."""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from config import DEFAULT_ACTIONS, DEFAULT_MAX_WORKERS, DEFAULT_USERS_FILE
from domain import Conta
from interfaces.repositories import IContaRepository
from interfaces.services import (
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

    def executar(self, acoes: Iterable[str] | None = None) -> None:
        """
        Orquestra a execução concorrente do processamento de contas.
        """
        acoes_normalizadas = self._normalizar_acoes(acoes or self._config.actions)
        contas = self._conta_repository.listar()
        
        if not contas:
            self._logger.aviso("Nenhuma conta encontrada para processar.")
            return

        self._proxy_service.start(threads=200, amounts=len(contas), auto_test=True)
        
        self._logger.info(
            "Iniciando processamento em lote com multithreading.",
            total_contas=len(contas),
            max_workers=self._config.max_workers
        )

        # Utiliza um ThreadPoolExecutor para gerenciar a execução concorrente
        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            # Submete cada tarefa de processamento de conta para o pool de threads
            futuros = {
                executor.submit(self._processar_conta, conta, acoes_normalizadas, proxy)
                for conta, proxy in zip(contas, self._proxy_service.get_http_proxy())
            }

            # Aguarda a conclusão de cada thread
            for futuro in as_completed(futuros):
                try:
                    # .result() irá propagar exceções que ocorreram dentro da thread
                    futuro.result()
                except Exception as exc:
                    self._logger.erro(
                        "Uma thread de processamento encontrou um erro inesperado e foi encerrada.",
                        erro=str(exc)
                    )
        
        self._logger.sucesso("Processamento em lote finalizado para todas as contas.")

    def _processar_conta(self, conta: Conta, acoes: Sequence[str], proxy: dict) -> None:
        """
        Este método é executado por cada thread de forma isolada.
        É seguro porque a 'sessao' é um objeto local, não compartilhado.
        """
        scoped_logger = self._logger.com_contexto(conta=conta.email)
        scoped_logger.info("Thread iniciada para processamento da conta.")

        try:
            self._perfil_service.garantir_perfil(conta.id_perfil, conta.email, conta.senha)
            
            # A chave da segurança: cada thread obtém sua própria sessão isolada.
            # A sessão contém BaseRequest, NetWork, cookies, etc., exclusivos para esta conta.
            sessao = self._autenticador.executar(conta, proxy=proxy) if "login" in acoes else None

            if sessao:
                # A partir daqui, a 'sessao' completa pode ser usada com segurança
                # para interagir com os serviços singleton.
                if "rewards" in acoes:
                    # Exemplo de uso
                    self._rewards_data.pegar_recompensas(sessao.base_request)
                    pontos = self._rewards_data.obter_pontos(sessao.base_request)
                    scoped_logger.info("Pontos atuais", pontos=pontos)

                if "solicitacoes" in acoes:
                    # Exemplo de uso
                    sugestoes = self._bing_search.get_all(sessao.base_request, "Brasil")
                    scoped_logger.info("Sugestões de busca encontradas", total=len(sugestoes))

            scoped_logger.sucesso("Conta processada com sucesso pela thread.")

        except Exception as exc:
            scoped_logger.erro("Falha ao processar conta na thread.", erro=str(exc))
            # Lança a exceção para que o loop principal em 'executar' possa capturá-la
            raise

    @staticmethod
    def _normalizar_acoes(acoes: Iterable[str]) -> list[str]:
        """Limpa e padroniza a lista de ações a serem executadas."""
        return [acao.strip().lower() for acao in acoes if acao and acao.strip()]

__all__ = ["ExecutorEmLote", "ExecutorConfig"]