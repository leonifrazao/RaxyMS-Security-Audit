"""
Serviço de Executor em Lote (BatchExecutor).

Responsável por orquestrar a execução paralela de tarefas em múltiplas contas.
Esta camada deve ser agnóstica de UI (não usa Rich diretamente).
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import cycle
from typing import List, Optional, Sequence, Any

from raxy.core.models import Conta, Proxy, ContaResult, ExecucaoResult
from raxy.core.interfaces import SessionStateRepository, NotificationService
from raxy.core.services.session_manager_service import SessionManagerService
from raxy.infrastructure.logging import get_logger

# Importações de adapters/services que serão usados
from raxy.adapters.api.rewards_data_api import RewardsDataAPI
from raxy.adapters.api.bing_suggestion_api import BingSuggestionAPI
# from raxy.core.services.bingflyout_service import BingFlyoutService # Assumindo que este será migrado também


class BatchExecutor:
    """Executor de tarefas em lote com suporte a paralelismo."""
    
    def __init__(
        self,
        state_repository: SessionStateRepository,
        max_workers: int = 4,
        mail_service: Optional[Any] = None,
        logger: Optional[Any] = None
    ):
        self.state_repository = state_repository
        self.max_workers = max_workers
        self.mail_service = mail_service
        self.logger = logger or get_logger()
        self._proxy_manager = None  # Será injetado ou inicializado sob demanda

    def executar(
        self,
        contas: Sequence[Conta],
        acoes: List[str],
        proxies: List[Proxy]
    ) -> ExecucaoResult:
        """
        Executa o lote de processamento.

        Args:
            contas: Lista de contas.
            acoes: Lista de ações (strings).
            proxies: Lista de proxies disponíveis.

        Returns:
            ExecucaoResult com estatísticas e detalhes.
        """
        resultado_geral = ExecucaoResult(total_contas=len(contas))
        
        if not contas:
            self.logger.aviso("Nenhuma conta fornecida para execução.")
            return resultado_geral
            
        # Garante "login"
        if "login" not in acoes:
            acoes = ["login"] + acoes
            
        proxy_cycle = cycle(proxies) if proxies else None
        
        self.logger.info(f"Iniciando batch: {len(contas)} contas, {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for conta in contas:
                proxy = next(proxy_cycle) if proxy_cycle else None
                future = executor.submit(self._processar_conta, conta, acoes, proxy)
                futures[future] = conta
            
            for future in as_completed(futures):
                try:
                    res = future.result()
                    resultado_geral.detalhes.append(res)
                    if res.sucesso_geral:
                        resultado_geral.sucessos += 1
                        resultado_geral.total_pontos += res.pontos_ganhos
                    else:
                        resultado_geral.falhas += 1
                except Exception as e:
                    # Captura erro catastrófico do worker não tratado
                    self.logger.erro(f"Erro no worker: {e}")
                    resultado_geral.falhas += 1
                    
        return resultado_geral

    def _processar_conta(
        self,
        conta: Conta,
        acoes: List[str],
        proxy: Optional[Proxy]
    ) -> ContaResult:
        """Processa uma única conta."""
        res = ContaResult(email=conta.email)
        logger = self.logger.com_contexto(conta=conta.email)
        sessao = None
        
        try:
            # Instancia SessionManager
            sessao = SessionManagerService(
                conta=conta,
                state_repository=self.state_repository,
                proxy=proxy,
                mail_service=self.mail_service,
                logger=logger
            )
            
            # --- 1. Login ---
            sessao.start()
            res.adicionar_etapa("login", True)
            if sessao.proxy:
                res.proxy_usado = sessao.proxy.url
            
            cookie_count = len(sessao.cookies) if sessao.cookies else 0
            logger.debug(f"Sessão pós-login possui {cookie_count} cookies")

            # --- 2. Setup APIs ---
            # Aqui idealmente teríamos uma Factory ou Injeção de Dependência
            rewards_api = RewardsDataAPI(session=sessao, logger=logger)
            bing_api = BingSuggestionAPI(logger=logger)
            # flyout = BingFlyoutService(...)

            # Pontos Iniciais
            try:
                res.pontos_iniciais = rewards_api.obter_pontos()
            except Exception:
                logger.aviso("Falha ao ler pontos iniciais")

            # --- 3. Executar Ações ---
            for acao in acoes:
                if acao == "login": continue
                
                try:
                    if acao == "rewards":
                        # Exemplo de chamada
                        ret = rewards_api.pegar_recompensas()
                        res.adicionar_etapa(acao, True, dados=ret)
                    elif acao == "bing":
                        # Bing search
                        sugs = bing_api.get_all("Brasil")
                        res.adicionar_etapa(acao, True, dados={"count": len(sugs)})
                    # elif acao == "flyout": ...
                    else:
                        logger.aviso(f"Ação desconhecida: {acao}")
                except Exception as err:
                    logger.erro(f"Erro na ação {acao}: {err}")
                    res.adicionar_etapa(acao, False, erro=str(err))

            # Pontos Finais
            try:
                res.pontos_finais = rewards_api.obter_pontos()
                res.pontos_ganhos = res.pontos_finais - res.pontos_iniciais
            except Exception:
                pass
            
            res.sucesso_geral = True
            logger.sucesso(f"Fim do processamento. +{res.pontos_ganhos} pontos.")

        except Exception as e:
            res.erro_fatal = str(e)
            res.sucesso_geral = False
            logger.erro(f"Falha na conta: {e}")
        finally:
            if sessao:
                try:
                    sessao.close()
                except Exception:
                    pass
        
        return res
