# raxy/services/executor_service.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Iterable, Sequence, Optional

from raxy.domain import Conta, InfraServices
from raxy.interfaces.services import IExecutorEmLoteService
from raxy.core.session_manager_service import SessionManagerService


# -------------------------------
# Configuração do Executor
# -------------------------------
@dataclass(slots=True)
class ExecutorConfig:
    """
    Contém todas as configurações para o Executor.
    Os valores padrão são definidos aqui e podem ser sobrescritos na inicialização.
    """
    # ALTERADO: Valores padrão movidos para cá, removendo a dependência do config.py
    users_file: str = "users.txt"
    actions: list[str] = field(default_factory=lambda: ["login", "rewards", "bing", "flyout"])
    max_workers: int = 2
    api_error_words: list[str] = field(default_factory=lambda: ["captcha", "verifique", "verify", "erro", "error", "unavailable"])
    use_proxies: bool = True
    proxy_workers: int = 200
    proxy_auto_test: bool = True
    proxy_amounts: Optional[int] = None


# -------------------------------
# Executor em Lote
# -------------------------------
class ExecutorEmLote(IExecutorEmLoteService):
    """
    Executor de fluxos em lote com integração ao ProxyManager.
    - Carrega proxies via ProxyManager
    - Testa e inicia pontes HTTP locais
    - Distribui proxies round-robin entre contas
    """

    def __init__(self, services: InfraServices, config: ExecutorConfig | None = None) -> None:
        self._config = config or ExecutorConfig()
        self._services = services

    # ---------------- execução principal ----------------
    def executar(self, acoes: Iterable[str] | None = None, contas: Sequence[Conta] | None = None) -> None:
        acoes_normalizadas = self._normalizar_acoes(acoes or self._config.actions)
        contas_processar = list(contas) if contas is not None else self._services.conta_repository.listar()

        if not contas_processar:
            self._services.logger.aviso("Nenhuma conta encontrada para processar.")
            return

        # Carregar e iniciar proxies
        proxies = self._services.proxy_manager.start(
            auto_test=self._config.proxy_auto_test,
            threads=self._config.proxy_workers,
            find_first=4
        )

        self._services.logger.info(
            "Iniciando processamento em lote com multithreading.",
            total_contas=len(contas_processar),
            max_workers=self._config.max_workers,
        )

        resultados: list[bool] = []
        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            futuros = {
                executor.submit(self._processar_conta, conta, acoes_normalizadas, proxy)
                for conta, proxy in zip(contas_processar, proxies)
            }

            for futuro in as_completed(futuros):
                try:
                    resultados.append(futuro.result())
                except Exception as exc:
                    self._services.logger.erro("Thread encontrou erro inesperado.", erro=str(exc))
                    resultados.append(False)

        # Resumo final
        if resultados and all(resultados):
            self._services.logger.sucesso("Processamento finalizado para todas as contas.")
        else:
            falhas = resultados.count(False)
            self._services.logger.aviso(f"Processamento finalizado com {falhas} falhas.")

    # ---------------- processamento individual ----------------
    def _processar_conta(self, conta: Conta, acoes: Sequence[str], proxy: dict[str, str] | None) -> bool:
        logger = self._services.logger.com_contexto(conta=conta.email)
        logger.info("Thread iniciada para conta.")

        try:
            # Login obrigatório
            if "login" not in acoes:
                logger.aviso("Ação 'login' ausente. Pulando.")
                return False

            sm = SessionManagerService(conta=conta, proxy=proxy or {}, proxy_service=self._services.proxy_manager)
            sm.start()

            pontos_iniciais = self._services.rewards_data.obter_pontos(sm)
            pontos_finais = pontos_iniciais
            logger.sucesso("Login bem-sucedido.", pontos_atual=pontos_iniciais)

            # Flyout (onboarding)
            if "flyout" in acoes:
                dados_flyout = self._services.bing_flyout_service.executar(sm)
                logger.info("Flyout processado", dados=dados_flyout)

            # Rewards
            if "rewards" in acoes:
                self._services.rewards_data.pegar_recompensas(sm)
                pontos_finais = self._services.rewards_data.obter_pontos(sm)
                if pontos_finais > pontos_iniciais:
                    logger.info("Recompensas coletadas", pontos_novos=pontos_finais - pontos_iniciais)
                else:
                    logger.aviso("Nenhum ponto adicional após recompensas no momento.")

            if "bing" in acoes:
                sugestoes = self._services.bing_search.get_all(sm, "Brasil")
                logger.info("Sugestões de busca encontradas", total=len(sugestoes))

            # Persistência no banco
            if pontos_finais > 0:
                self._services.db_repository.adicionar_registro_farm(email=conta.email, pontos=pontos_finais)
            else:
                logger.aviso("Pontuação final não determinada; banco ignorado.")

            logger.sucesso("Conta processada com sucesso.")
            return True

        except Exception as exc:
            logger.erro("Falha ao processar conta.", erro=str(exc))
            return False

    # ---------------- util ----------------
    @staticmethod
    def _normalizar_acoes(acoes: Iterable[str]) -> list[str]:
        """Normaliza lista de ações para minúsculas e sem espaços extras."""
        return [acao.strip().lower() for acao in acoes if acao and acao.strip()]
