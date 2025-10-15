# raxy/services/executor_service.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Iterable, Sequence, Optional, List

from raxy.config import DEFAULT_ACTIONS, DEFAULT_MAX_WORKERS, DEFAULT_USERS_FILE, WORKERS_PROXY
from raxy.domain import Conta
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import (
    IExecutorEmLoteService,
    ILoggingService,
    IPerfilService,
    IRewardsDataService,
    IBingSuggestion,
    IBingFlyoutService,
    IProxyService
)
from raxy.core.session_manager_service import SessionManagerService


@dataclass(slots=True)
class ExecutorConfig:
    users_file: str = DEFAULT_USERS_FILE
    actions: list[str] = field(default_factory=lambda: list(DEFAULT_ACTIONS))
    max_workers: int = DEFAULT_MAX_WORKERS
    api_error_words: list[str] = field(default_factory=list)
    use_proxies: bool = True
    proxy_workers: int = WORKERS_PROXY
    proxy_auto_test: bool = True
    proxy_amounts: Optional[int] = None  # limite de pontes simultâneas (None = todas as aprovadas)


class ExecutorEmLote(IExecutorEmLoteService):
    """
    Executor de fluxos em lote com integração ao ProxyManager simplificado (V2Ray/Xray).
    - Carrega proxies via ProxyManager
    - Testa e inicia pontes HTTP locais
    - Distribui proxies round-robin entre contas
    """

    def __init__(
        self,
        *,
        bing_search: IBingSuggestion,
        conta_repository: IContaRepository,
        perfil_service: IPerfilService,
        rewards_data: IRewardsDataService,
        logger: ILoggingService,
        db_repository: IDatabaseRepository,
        bing_flyout_service: IBingFlyoutService,
        config: ExecutorConfig | None = None,
        proxy_manager: IProxyService | None = None,
    ) -> None:
        self._config = config or ExecutorConfig()
        self._logger = logger
        self._perfil_service = perfil_service
        self._conta_repository = conta_repository
        self._rewards_data = rewards_data
        self._bing_search = bing_search
        self._db_repository = db_repository
        self._bing_flyout_service = bing_flyout_service
        self._proxy_manager = proxy_manager

    # ---------------- execução principal ----------------

    def executar(self, acoes: Iterable[str] | None = None, contas: Sequence[Conta] | None = None) -> None:
        acoes_normalizadas = self._normalizar_acoes(acoes or self._config.actions)
        contas_processar = list(contas) if contas is not None else self._conta_repository.listar()

        if not contas_processar:
            self._logger.aviso("Nenhuma conta encontrada para processar.")
            return

        # Proxies: carregar, testar e iniciar pontes
        urls = self._proxy_manager.start(auto_test=True, threads=self._config.proxy_workers, find_first=4)

        self._logger.info(
            "Iniciando processamento em lote com multithreading.",
            total_contas=len(contas_processar),
            max_workers=self._config.max_workers,
        )

        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            futuros = {
                executor.submit(self._processar_conta, conta, acoes_normalizadas, proxy)
                for conta, proxy in zip(contas_processar, urls)
            }

            resultados = []
            for futuro in as_completed(futuros):
                try:
                    resultados.append(futuro.result())
                except Exception as exc:
                    self._logger.erro("Thread encontrou erro inesperado.", erro=str(exc))

        if resultados and all(resultados):
            self._logger.sucesso("Processamento finalizado para todas as contas.")
        else:
            falhas = resultados.count(False)
            self._logger.aviso(f"Processamento finalizado com {falhas} falhas.")


    # ---------------- processamento individual ----------------

    def _processar_conta(self, conta: Conta, acoes: Sequence[str], proxy: List[str]) -> bool:
        scoped_logger = self._logger.com_contexto(conta=conta.email)
        scoped_logger.info("Thread iniciada para conta.")

        sm: Optional[SessionManagerService] = None

        try:
            # Perfil
            self._perfil_service.garantir_perfil(conta.id_perfil, conta.email, conta.senha)

            conta = Conta(email=conta.email, senha=conta.senha, id_perfil=conta.id_perfil, proxy=proxy)

            # Login é obrigatório
            if "login" not in acoes:
                scoped_logger.aviso("Ação 'login' ausente. Pulando.")
                return False

            sm = SessionManagerService(conta=conta, proxy={"url": conta.proxy["url"]} if conta.proxy else {})
            sm.start()

            pontos_iniciais = self._rewards_data.obter_pontos(sm)
            pontos_finais = pontos_iniciais
            scoped_logger.sucesso("Login bem-sucedido.", pontos_atual=pontos_iniciais)

            # Flyout (onboarding)
            if "flyout" in acoes:
                dados_flyout = self._bing_flyout_service.executar(sm)
                scoped_logger.info("Flyout processado", dados=dados_flyout)

            # Rewards (pegar recompensas + atualizar pontuação)
            if "rewards" in acoes:
                self._rewards_data.pegar_recompensas(sm)
                pontos_finais = self._rewards_data.obter_pontos(sm)
                if pontos_finais > pontos_iniciais:
                    scoped_logger.info("Pontos atuais", pontos=pontos_finais)
                else:
                    scoped_logger.aviso("Nenhum ponto adicional após recompensas.", pontos=pontos_finais)

            # Solicitações (sugestões de busca)
            if "solicitacoes" in acoes:
                sugestoes = self._bing_search.get_all(sm, "Brasil")
                scoped_logger.info("Sugestões de busca encontradas", total=len(sugestoes))

            # Persistência no banco
            if pontos_finais > 0:
                self._db_repository.adicionar_registro_farm(email=conta.email, pontos=pontos_finais)
            else:
                scoped_logger.aviso("Pontuação final não determinada; banco ignorado.")

            scoped_logger.sucesso("Conta processada com sucesso.")
            return True

        except Exception as exc:
            scoped_logger.erro("Falha ao processar conta.", erro=str(exc))
            return False

    # ---------------- util ----------------

    @staticmethod
    def _normalizar_acoes(acoes: Iterable[str]) -> list[str]:
        return [acao.strip().lower() for acao in acoes if acao and acao.strip()]
