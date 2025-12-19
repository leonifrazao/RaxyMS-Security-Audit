"""
Serviço de execução em lote simplificado.

Gerencia a execução paralela de tarefas para múltiplas contas
com suporte a proxies e tratamento de erros.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from itertools import cycle
from typing import Dict, List, Optional, Sequence, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from raxy.core.domain import Conta
from raxy.core.domain.proxy import Proxy
from raxy.core.domain.execution import ContaResult
from raxy.core.services.session_manager_service import SessionManagerService
from raxy.infrastructure.config.config import get_config
from raxy.infrastructure.logging import get_logger


class ExecutorEmLote:
    """
    Executor de fluxos em lote com processamento paralelo.
    
    Uso simples:
        executor = ExecutorEmLote()
        resultado = executor.executar(contas, acoes=["login", "bing", "rewards"])
    """
    
    def __init__(self, max_workers: int = 4, logger=None):
        self.logger = logger or get_logger()
        self.max_workers = max_workers
        self._resultados: List[ContaResult] = []
        self.proxy_manager = None
    
    def executar(
        self,
        contas: Sequence[Conta],
        acoes: Optional[List[str]] = None,
        usar_proxy: bool = True,
    ) -> Dict[str, Any]:
        """
        Executa o processamento em lote.
        
        Args:
            contas: Contas a processar
            acoes: Ações a executar (ex: ["login", "bing", "rewards"])
            usar_proxy: Se deve usar proxies
            
        Returns:
            Dict com estatísticas da execução
        """
        self._resultados = []
        
        if not contas:
            self.logger.aviso("Nenhuma conta para processar")
            return self._get_resumo()
        
        # Normaliza ações
        acoes = acoes or ["login", "bing", "rewards"]
        if "login" not in acoes:
            acoes = ["login"] + acoes
        
        # Prepara proxies
        proxies = self._carregar_proxies() if usar_proxy else []
        proxy_cycle = cycle(proxies) if proxies else None
        
        self.logger.info(f"Iniciando execução: {len(contas)} contas, {len(acoes)} ações")
        
        # Processa em paralelo
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for conta in contas:
                proxy = next(proxy_cycle) if proxy_cycle else None
                future = executor.submit(self._processar_conta, conta, acoes, proxy)
                futures[future] = conta
            
            for future in as_completed(futures):
                try:
                    resultado = future.result()
                    self._resultados.append(resultado)
                except Exception as e:
                    conta = futures[future]
                    self._resultados.append(ContaResult(
                        email=conta.email,
                        sucesso_geral=False,
                        erro_fatal=str(e)
                    ))
        
        resumo = self._get_resumo()
        self._exibir_resumo(resumo)
        return resumo
    
    def _processar_conta(
        self,
        conta: Conta,
        acoes: List[str],
        proxy: Optional[Proxy]
    ) -> ContaResult:
        """Processa uma conta individual."""
        resultado = ContaResult(email=conta.email, sucesso_geral=False)
        logger = self.logger.com_contexto(conta=conta.email)
        sessao = None
        
        try:
            # Login - cria sessão
            logger.info("Iniciando login...")
            sessao = SessionManagerService(
                conta=conta,
                proxy=proxy,
                logger=logger
            )
            sessao.start()
            resultado.adicionar_etapa("login", True)
            
            # Registra proxy usado
            if sessao.proxy:
                resultado.proxy_usado = sessao.proxy.url
            
            # Cria APIs com a sessão
            from raxy.adapters.api.rewards_data_api import RewardsDataAPI
            from raxy.adapters.api.bing_suggestion_api import BingSuggestionAPI
            from raxy.core.services.bingflyout_service import BingFlyoutService
            
            rewards_api = RewardsDataAPI(session=sessao, logger=logger)
            bing_api = BingSuggestionAPI(logger=logger)
            flyout_service = BingFlyoutService(logger=logger)
            
            # Obter pontos iniciais
            try:
                resultado.pontos_iniciais = rewards_api.obter_pontos()
            except Exception as e:
                logger.aviso(f"Não foi possível obter pontos iniciais: {e}")
            
            # Executar ações
            for acao in acoes:
                if acao == "login":
                    continue
                
                try:
                    dados_acao = self._executar_acao(acao, sessao, rewards_api, bing_api, flyout_service, logger)
                    resultado.adicionar_etapa(acao, True, dados=dados_acao)
                except Exception as e:
                    resultado.adicionar_etapa(acao, False, erro=str(e))
            
            # Obter pontos finais
            try:
                resultado.pontos_finais = rewards_api.obter_pontos()
                resultado.pontos_ganhos = resultado.pontos_finais - resultado.pontos_iniciais
            except Exception as e:
                logger.aviso(f"Não foi possível obter pontos finais: {e}")
            
            resultado.sucesso_geral = True
            logger.sucesso(f"+{resultado.pontos_ganhos} pontos")
            
        except Exception as e:
            resultado.erro_fatal = str(e)
            logger.erro(f"Erro: {e}")
        
        finally:
            if sessao:
                try:
                    sessao.close()
                except Exception as e:
                    logger.aviso(f"Erro ao fechar sessão: {e}")
        
        return resultado
    
    def _executar_acao(
        self,
        acao: str,
        sessao: SessionManagerService,
        rewards_api,
        bing_api,
        flyout_service,
        logger
    ):
        """Executa uma ação específica."""
        if acao == "bing":
            # Bing search não precisa de sessão autenticada
            sugestoes = bing_api.get_all("Brasil")
            logger.debug(f"Bing: {len(sugestoes)} sugestões")
            return {"sugestoes_count": len(sugestoes)}
        
        elif acao == "rewards":
            return rewards_api.pegar_recompensas()
        
        elif acao == "flyout":
            return flyout_service.executar(sessao)
        
        else:
            logger.aviso(f"Ação desconhecida: {acao}")
            return None
    
    def _carregar_proxies(self) -> List[Proxy]:
        """Carrega proxies disponíveis."""
        try:
            # Se já tem manager rodando, retorna as proxies atuais
            if self.proxy_manager and self.proxy_manager._running:
                proxies_raw = self.proxy_manager.get_http_proxy()
                return [
                    Proxy(
                        id=p.get("tag", str(p.get("id"))),
                        url=p.get("url", ""),
                        type=p.get("scheme", "http"),
                        country=p.get("country_code"),
                    )
                    for p in proxies_raw
                ]

            from raxy.infrastructure.manager import ProxyManager
            config = get_config()
            
            # Carrega sources do config
            sources = config.proxy.sources if hasattr(config, 'proxy') else None
            
            # Inicializa manager
            self.proxy_manager = ProxyManager(sources=sources, use_console=False)
            
            # Inicia proxies (auto_test=True para validar)
            # wait=False para não bloquear a execução
            proxies_raw = self.proxy_manager.start(
                auto_test=True,
                threads=self.max_workers,
                country=config.proxy.country,
                find_first=20,
                wait=False
            )
            
            self.logger.info(f"Proxies carregados: {len(proxies_raw)}")
            
            return [
                Proxy(
                    id=p.get("tag", ""),
                    url=p.get("url", ""),
                    type=p.get("scheme", "http"),
                    country=p.get("country_code"),
                )
                for p in proxies_raw
            ]
        except Exception as e:
            self.logger.erro(f"Erro ao carregar proxies: {e}")
            return []
    
    def _get_resumo(self) -> Dict[str, Any]:
        """Gera resumo da execução."""
        total = len(self._resultados)
        sucesso = sum(1 for r in self._resultados if r.sucesso_geral)
        pontos = sum(r.pontos_ganhos for r in self._resultados)
        
        return {
            "total": total,
            "sucesso": sucesso,
            "falha": total - sucesso,
            "pontos_totais": pontos,
            "taxa_sucesso": f"{(sucesso/total*100):.1f}%" if total > 0 else "0%",
            "resultados": [
                {
                    "email": r.email,
                    "sucesso": r.sucesso_geral,
                    "pontos_ganhos": r.pontos_ganhos,
                    "erro": r.erro_fatal,
                }
                for r in self._resultados
            ]
        }
    
    def _exibir_resumo(self, resumo: Dict[str, Any]):
        """Exibe resumo formatado no console."""
        console = Console()
        
        tabela = Table(title="📋 Resumo da Execução", box=box.ROUNDED)
        tabela.add_column("Métrica", style="cyan")
        tabela.add_column("Valor", style="magenta", justify="right")
        
        tabela.add_row("Total", str(resumo["total"]))
        tabela.add_row("Sucesso", f"[green]{resumo['sucesso']}[/green]")
        tabela.add_row("Falha", f"[red]{resumo['falha']}[/red]")
        tabela.add_row("Pontos", f"[yellow]+{resumo['pontos_totais']}[/yellow]")
        
        console.print("\n")
        console.print(tabela)
        
        cor = "green" if resumo["falha"] == 0 else "yellow"
        console.print(Panel(
            f"[bold {cor}]{resumo['taxa_sucesso']} sucesso | +{resumo['pontos_totais']} pontos[/bold {cor}]",
            border_style=cor
        ))
