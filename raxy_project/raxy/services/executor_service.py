"""
Serviço de execução em lote refatorado.

Gerencia a execução paralela de tarefas para múltiplas contas
com suporte a proxies, logging estruturado e tratamento robusto de erros.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Any
import random

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from raxy.models import Conta, InfraServices
from raxy.models.execution import BatchExecutionResult, ContaResult, EtapaResult
from raxy.models.proxy import ProxyItem
from raxy.infrastructure.session.session_manager import SessionManager
from raxy.core.config import ExecutorConfig, ProxyConfig
from raxy.core.exceptions import (
    InvalidCredentialsException,
    ProxyRotationRequiredException,
    SessionException,
    LoginException,
    TaskExecutionException,
    ExecutionException,
    wrap_exception,
)
from raxy.core.logging import debug_log
from raxy.interfaces.services import IExecutorEmLoteService, ILoggingService, IDashboardService
from .base_service import BaseService
import time


# Local definitions of EtapaResult and ContaResult removed in favor of raxy.models.execution
# Using imported classes instead.


class ExecutionStats:
    """Estatísticas de execução."""
    
    def __init__(self):
        """Inicializa estatísticas."""
        self.total_contas = 0
        self.contas_sucesso = 0
        self.contas_falha = 0
        self.pontos_totais = 0
        self.resultados_contas: List[ContaResult] = []
    
    def add_result(self, resultado: ContaResult) -> None:
        """Adiciona resultado de uma conta."""
        self.resultados_contas.append(resultado)
        
        if resultado.sucesso_geral:
            self.contas_sucesso += 1
            self.pontos_totais += resultado.pontos_ganhos
        else:
            self.contas_falha += 1
    
    def get_summary(self) -> BatchExecutionResult:
        """Retorna resumo das estatísticas como objeto de domínio."""
        return BatchExecutionResult(
            total_contas=self.total_contas,
            contas_sucesso=self.contas_sucesso,
            contas_falha=self.contas_falha,
            pontos_totais=self.pontos_totais,
            resultados_detalhados=self.resultados_contas
        )


class AccountProcessor:
    """Processador de conta individual."""
    
    def __init__(
        self,
        rewards_service,
        bing_search_service,
        flyout_service,
        proxy_service,
        mail_service,
        db_repository,
        logger: ILoggingService,
        dashboard_service: Optional[IDashboardService] = None,
        debug: bool = False
    ):
        """
        Inicializa o processador com dependências específicas.
        
        Args:
            rewards_service: Serviço de recompensas (IRewardsDataService)
            bing_search_service: Serviço de busca Bing (IBingSuggestion)
            flyout_service: Serviço de flyout (IBingFlyoutService)
            proxy_service: Serviço de proxy (IProxyService)
            mail_service: Serviço de email (IMailTmService)
            db_repository: Repositório de banco de dados (IDatabaseRepository)
            logger: Serviço de logging
            dashboard_service: Serviço de dashboard (IDashboardService)
            debug: Se está em modo debug
        """
        # Dependências específicas - melhor desacoplamento
        self.rewards_service = rewards_service
        self.bing_search_service = bing_search_service
        self.flyout_service = flyout_service
        self.proxy_service = proxy_service
        self.mail_service = mail_service
        self.db_repository = db_repository
        self.logger = logger
        self.dashboard = dashboard_service
        self.debug = debug

    
    @debug_log(log_args=False, log_result=False, log_duration=True)
    def process(
        self,
        conta: Conta,
        acoes: Sequence[str],
        proxy: Optional[ProxyItem] = None
    ) -> ContaResult:
        """
        Processa uma conta individual.
        
        Args:
            conta: Conta a processar
            acoes: Ações a executar
            proxy: Proxy a usar
            
        Returns:
            ContaResult: Resultado detalhado do processamento
        """
        # Inicializa resultado
        resultado = ContaResult(
            email=conta.email,
            sucesso_geral=False,
            proxy_usado=proxy.tag if proxy else None
        )
        
        # Logger com contexto da conta
        logger = self.logger.com_contexto(
            conta=conta.email,
            proxy=resultado.proxy_usado
        )
        
        sessao = None
        
        try:
            # Valida ações
            if "login" not in acoes:
                acoes = ["login"] + list(acoes)
            
            # Notifica inicio
            if self.dashboard:
                self.dashboard.update_worker(conta.email, conta.email, "Iniciando...")

            # Etapa 1: Login/Criar sessão
            try:
                if self.dashboard:
                    self.dashboard.update_worker(conta.email, conta.email, "Login")
                    
                sessao = self._criar_sessao(conta, proxy, logger)
                resultado.adicionar_etapa("login", True, dados={"email": conta.email})
            except (InvalidCredentialsException, LoginException) as e:
                erro_msg = f"Credenciais inválidas: {str(e)}"
                resultado.adicionar_etapa("login", False, erro=erro_msg)
                resultado.erro_fatal = f"Falha no login: {str(e)}"
                logger.erro(f"Falha de autenticação", error=erro_msg)
                if self.dashboard:
                    self.dashboard.increment_failure()
                    self.dashboard.update_worker(conta.email, conta.email, "[red]Falha Login[/red]")
                    self.dashboard.worker_done(conta.email)
                return resultado
            except SessionException as e:
                erro_msg = f"Erro de sessão: {str(e)}"
                resultado.adicionar_etapa("login", False, erro=erro_msg)
                resultado.erro_fatal = f"Falha na sessão: {str(e)}"
                logger.erro(f"Falha na sessão", error=erro_msg)
                if self.dashboard:
                    self.dashboard.increment_failure()
                    self.dashboard.update_worker(conta.email, conta.email, "[red]Erro Sessão[/red]")
                    self.dashboard.worker_done(conta.email)
                return resultado
            except Exception as e:
                erro_msg = f"Erro inesperado: {str(e)}"
                resultado.adicionar_etapa("login", False, erro=erro_msg)
                resultado.erro_fatal = erro_msg
                logger.erro(f"Erro inesperado no login", error=erro_msg, exception=e)
                return resultado
            
            # Etapa 2: Obter pontos iniciais
            resultado.pontos_iniciais = self._obter_pontos(sessao, logger)
            resultado.adicionar_etapa(
                "obter_pontos_iniciais",
                True,
                dados={"pontos": resultado.pontos_iniciais}
            )
            
            # Etapa 3: Executar ações
            for acao in acoes:
                if acao == "login":
                    continue  # Já feito na criação da sessão
                
                if self.dashboard:
                    self.dashboard.update_worker(conta.email, conta.email, f"Executando {acao}...")
                    
                sucesso_acao, erro_acao = self._executar_acao_com_resultado(acao, sessao, logger)
                
                if sucesso_acao:
                    logger.debug(f"Ação '{acao}' concluída com sucesso")
                else:
                    logger.aviso(f"Ação '{acao}' falhou", erro=erro_acao)
                    
                resultado.adicionar_etapa(acao, sucesso_acao, erro=erro_acao)
            
            # Etapa 4: Obter pontos finais
            if self.dashboard:
                self.dashboard.update_worker(conta.email, conta.email, "Finalizando...")
                
            resultado.pontos_finais = self._obter_pontos(sessao, logger)
            resultado.pontos_ganhos = resultado.pontos_finais - resultado.pontos_iniciais
            resultado.adicionar_etapa(
                "obter_pontos_finais",
                True,
                dados={
                    "pontos_finais": resultado.pontos_finais,
                    "pontos_ganhos": resultado.pontos_ganhos
                }
            )
            
            # Etapa 5: Salvar no banco
            # Removido check de > 0 para garantir update de ultima_farm
            logger.info(f"Salvando dados no banco: {conta.email} - {resultado.pontos_finais} pts")
            try:
                self._salvar_no_banco(conta.email, resultado.pontos_finais, logger)
                resultado.adicionar_etapa("salvar_banco", True)
            except Exception as e:
                resultado.adicionar_etapa("salvar_banco", False, erro=str(e))
            
            # Marca como sucesso geral
            resultado.sucesso_geral = True
            
            if self.dashboard:
                self.dashboard.increment_success()
                self.dashboard.update_worker(conta.email, conta.email, "[green]Concluído[/green]")
                self.dashboard.worker_done(conta.email)
                
            return resultado
            
        except Exception as e:
            resultado.erro_fatal = f"Erro crítico: {str(e)}"
            logger.erro(f"Erro crítico no processamento", error=str(e), exception=e)
            
            if self.dashboard:
                self.dashboard.increment_failure()
                self.dashboard.update_worker(conta.email, conta.email, "[red]Erro Crítico[/red]")
                self.dashboard.worker_done(conta.email)
                
            return resultado
    
    def _criar_sessao(
        self,
        conta: Conta,
        proxy: Optional[ProxyItem],
        logger: ILoggingService
    ) -> SessionManager:
        """Cria e inicializa sessão."""
        sessao = SessionManager(
            conta=conta,
            proxy=proxy,
            proxy_service=self.proxy_service,
            mail_service=self.mail_service,
            logger=logger
        )
        sessao.start()
        return sessao
    
    def _obter_pontos(self, sessao: SessionManager, logger: ILoggingService) -> int:
        """Obtém pontos da conta."""
        try:
            pontos = self.rewards_service.obter_pontos(sessao)
            return pontos
        except Exception as e:
            return 0
    
    def _executar_acao_com_resultado(
        self,
        acao: str,
        sessao: SessionManager,
        logger: ILoggingService
    ) -> tuple[bool, Optional[str]]:
        """Executa uma ação específica e retorna resultado.
        
        Returns:
            tuple[bool, Optional[str]]: (sucesso, mensagem_erro)
        """
        try:
            if acao == "flyout":
                self.flyout_service.executar(sessao)
                return True, None
                
            elif acao == "rewards":
                self.rewards_service.pegar_recompensas(sessao)
                return True, None
                
            elif acao == "bing":
                # 1. Busca PC
                if not self.bing_search_service.realizar_ciclo_pesquisa(sessao, self.rewards_service, mobile=False):
                     return False, "Falha na busca PC"

                # 2. Busca Mobile
                if not self.bing_search_service.realizar_ciclo_pesquisa(sessao, self.rewards_service, mobile=True):
                     return False, "Falha na busca Mobile"
                
                return True, None
                
            else:
                return False, f"Ação desconhecida: {acao}"

        except Exception as e:
            erro_msg = f"{type(e).__name__}: {str(e)}"
            if self.debug or logger:
                 logger.aviso(f"Erro na etapa '{acao}'", erro=erro_msg, exception=e)
            return False, erro_msg


    
    def _salvar_no_banco(
        self,
        email: str,
        pontos: int,
        logger: ILoggingService
    ) -> None:
        """Salva registro no banco de dados."""
        try:
            if self.db_repository:
                self.db_repository.adicionar_registro_farm(email, pontos)
        except Exception as e:
            if logger:
                logger.erro(f"Erro ao salvar no banco: {str(e)}", exception=e)
            pass


class ExecutorEmLote(BaseService, IExecutorEmLoteService):
    """
    Executor de fluxos em lote com processamento paralelo.
    
    Gerencia a execução de tarefas para múltiplas contas
    com suporte a proxies e tratamento robusto de erros.
    """
    
    def __init__(
        self,
        services: InfraServices,
        config: Optional[ExecutorConfig] = None,
        proxy_config: Optional[ProxyConfig] = None,
        logger: Optional[ILoggingService] = None
    ) -> None:
        """
        Inicializa o executor.
        
        Args:
            services: Serviços de infraestrutura
            config: Configuração do executor
            proxy_config: Configuração de proxy
        """
        super().__init__(logger)
        self._config = config or ExecutorConfig()
        self._proxy_config = proxy_config or ProxyConfig()
        self._services = services
        
        # Injeção de dependências específicas (melhor desacoplamento)
        self._processor = AccountProcessor(
            rewards_service=services.rewards_data,
            bing_search_service=services.bing_search,
            flyout_service=services.bing_flyout_service,
            proxy_service=services.proxy_manager,
            mail_service=services.mail_tm_service,
            db_repository=services.db_repository,
            logger=self.logger,
            dashboard_service=services.dashboard,
            debug=self._config.debug
        )
        self._stats = ExecutionStats()
    
    @debug_log(log_args=False, log_result=False, log_duration=True)
    def executar(
        self,
        acoes: Optional[Iterable[str]] = None,
        contas: Optional[Sequence[Conta]] = None
    ) -> BatchExecutionResult:
        """
        Executa o processamento em lote.
        
        Args:
            acoes: Ações a executar (usa config se None)
            contas: Contas a processar (busca do repositório se None)
            
        Returns:
            BatchExecutionResult: Estatísticas da execução
            
        Raises:
            ExecutionException: Se erro crítico na execução
        """
        
        try:
            with self.logger.etapa("Execução em Lote"):
                # Prepara ações
                acoes_norm = self._preparar_acoes(acoes)
                
                # Carrega contas
                contas_proc = self._carregar_contas(contas)
                if not contas_proc:
                    self.logger.aviso("Nenhuma conta para processar")
                    return self._stats.get_summary()
                
                # Inicializa estatísticas
                self._stats.total_contas = len(contas_proc)
                
                # Inicia dashboard
                if self._services.dashboard:
                    self._services.dashboard.start(len(contas_proc))
                
                # Prepara proxies se necessário
                proxies = self._preparar_proxies() if self._proxy_config.enabled else []
                
                # Executa processamento paralelo
                self._processar_paralelo(contas_proc, acoes_norm, proxies)
                
                # Retorna estatísticas
                resumo = self._stats.get_summary()
                
                # Para dashboard antes de imprimir resumo final
                if self._services.dashboard:
                    self._services.dashboard.stop()
                    
                self._log_resumo(resumo)
                
                return resumo
        
        finally:
            # Garante que dashboard pare em caso de erro
            if self._services.dashboard:
                self._services.dashboard.stop()
    
    def _preparar_acoes(self, acoes: Optional[Iterable[str]]) -> List[str]:
        """
        Prepara e normaliza ações.
        
        Args:
            acoes: Ações fornecidas
            
        Returns:
            List[str]: Ações normalizadas
        """
        try:
            acoes_usar = acoes or self._config.actions
            return self._normalizar_acoes(acoes_usar)
        except Exception as e:
            self.handle_error(e, {"context": "normalização de ações"})
    
    def _carregar_contas(self, contas: Optional[Sequence[Conta]]) -> List[Conta]:
        """
        Carrega contas para processar.
        
        Args:
            contas: Contas fornecidas
            
        Returns:
            List[Conta]: Lista de contas
        """
        try:
            if contas is not None:
                return list(contas)
            
            return self._services.conta_repository.listar()
        except Exception as e:
            self.handle_error(e, {"context": "carregamento de contas"})
    
    def _preparar_proxies(self) -> List[Dict[str, str]]:
        """
        Prepara proxies para uso.
        
        Returns:
            List[ProxyItem]: Lista de proxies
        """
        try:
            if self._services.dashboard:
                self._services.dashboard.set_global_status("🔄 Buscando e testando proxies (isso pode demorar)...")

            proxies = self._services.proxy_manager.start(
                auto_test=self._proxy_config.auto_test,
                threads=self._config.max_workers,
                find_first=20
            )
            
            if self._services.dashboard:
                self._services.dashboard.set_global_status(f"✅ Executando com {len(proxies)} proxies")
                
            self.logger.info(f"Proxies encontrados: {len(proxies)}", extra={"proxies": [p.uri for p in proxies[:5]]})
            return proxies
        except Exception as e:
            self.logger.erro(f"Erro ao preparar proxies: {str(e)}", exception=e)
            if self._services.dashboard:
                self._services.dashboard.set_global_status(f"❌ Erro ao buscar proxies: {str(e)}")
            return []
    
    def _processar_paralelo(
        self,
        contas: List[Conta],
        acoes: List[str],
        proxies: List[ProxyItem]
    ) -> None:
        """
        Processa contas em paralelo.
        
        Args:
            contas: Contas a processar
            acoes: Ações a executar
            proxies: Proxies disponíveis
        """
        pass
        
        # Distribui proxies ciclicamente se houver menos que contas
        if proxies:
            from itertools import cycle
            proxy_cycle = cycle(proxies)
            proxy_map = {conta: next(proxy_cycle) for conta in contas}
        else:
            proxy_map = {conta: None for conta in contas}
        
        # Log da distribuição de proxies
        if proxies:
             self.logger.debug("Mapa de distribuição de proxies gerado", extra={
                 "map": {c.email: (p.tag if p else "None") for c, p in list(proxy_map.items())[:10]}
             })
        
        # Executa em paralelo
        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            futuros = {
                executor.submit(
                    self._processar_conta_wrapper,
                    conta,
                    acoes,
                    proxy_map[conta]
                ): conta
                for conta in contas
            }
            
            # Processa resultados conforme completam
            for futuro in as_completed(futuros):
                conta = futuros[futuro]
                
                try:
                    resultado = futuro.result()
                    self._stats.add_result(resultado)
                        
                except Exception as e:
                    # Cria resultado de erro
                    resultado_erro = ContaResult(
                        email=conta.email,
                        sucesso_geral=False,
                        erro_fatal=f"Erro no processamento paralelo: {str(e)}"
                    )
                    self._stats.add_result(resultado_erro)
    
    def _processar_conta_wrapper(
        self,
        conta: Conta,
        acoes: List[str],
        proxy: Optional[ProxyItem]
    ) -> ContaResult:
        """
        Wrapper para processar conta com tratamento de erros.
        
        Args:
            conta: Conta a processar
            acoes: Ações a executar
            proxy: Proxy a usar
            
        Returns:
            ContaResult: Resultado do processamento
        """
        try:
            return self._processor.process(conta, acoes, proxy)
        except Exception as e:
            return ContaResult(
                email=conta.email,
                sucesso_geral=False,
                erro_fatal=f"Erro no wrapper: {str(e)}",
                proxy_usado=proxy.tag if proxy else None
            )
    
    def _log_resumo(self, resumo: BatchExecutionResult) -> None:
        """
        Registra resumo da execução com tabela formatada.
        
        Args:
            resumo: Resumo das estatísticas
        """
        console = Console()
        
        # Tabela de resumo geral
        tabela_geral = Table(title="📋 Resumo da Execução", box=box.ROUNDED, show_header=True, header_style="bold cyan")
        tabela_geral.add_column("Métrica", style="cyan", width=20)
        tabela_geral.add_column("Valor", style="magenta", justify="right")
        
        tabela_geral.add_row("Total de Contas", str(resumo.total_contas))
        tabela_geral.add_row("Sucessos", f"[green]{resumo.contas_sucesso}[/green]")
        tabela_geral.add_row("Falhas", f"[red]{resumo.contas_falha}[/red]")
        tabela_geral.add_row("Pontos Totais", f"[yellow]{resumo.pontos_totais}[/yellow]")
        
        taxa = (resumo.contas_sucesso / resumo.total_contas * 100) if resumo.total_contas > 0 else 0
        tabela_geral.add_row("Taxa de Sucesso", f"[bold]{taxa:.1f}%[/bold]")
        
        console.print("\n")
        console.print(tabela_geral)
        
        # Tabela detalhada de contas
        if resumo.resultados_detalhados:
            console.print("\n")
            tabela_contas = Table(
                title="👥 Detalhes por Conta", 
                box=box.ROUNDED, 
                show_header=True, 
                header_style="bold yellow"
            )
            tabela_contas.add_column("Email", style="cyan", no_wrap=False, width=30)
            tabela_contas.add_column("Status", justify="center", width=8)
            tabela_contas.add_column("Pts Totais", justify="right", style="yellow", width=11)
            tabela_contas.add_column("Pts Ganhos", justify="right", style="green bold", width=11)
            tabela_contas.add_column("Etapas ✓", justify="center", style="green", width=9)
            tabela_contas.add_column("Etapas ✗", justify="center", style="red", width=9)
            
            if self._config.debug:
                tabela_contas.add_column("Erro", style="red dim", width=40)
            
            for resultado in resumo.resultados_detalhados:
                status_icon = "✅" if resultado.sucesso_geral else "❌"
                ganhos_str = f"+{resultado.pontos_ganhos}" if resultado.pontos_ganhos > 0 else str(resultado.pontos_ganhos)
                
                etapas_ok = sum(1 for e in resultado.etapas if e.sucesso)
                etapas_falha = len(resultado.etapas) - etapas_ok

                row_data = [
                    resultado.email,
                    status_icon,
                    str(resultado.pontos_finais),
                    ganhos_str,
                    str(etapas_ok),
                    str(etapas_falha)
                ]
                
                if self._config.debug:
                    erro = resultado.erro_fatal or "-"
                    if erro and len(erro) > 40:
                        erro = erro[:37] + "..."
                    row_data.append(erro)
                
                tabela_contas.add_row(*row_data)
            
            console.print(tabela_contas)
        
        # Mensagem final
        console.print("\n")
        if resumo.contas_falha == 0:
            console.print(Panel(
                f"[bold green] Processamento concluído com sucesso! {resumo.pontos_totais} pontos obtidos.[/bold green]",
                border_style="green",
                box=box.DOUBLE
            ))
        else:
            console.print(Panel(
                f"[bold yellow] Processamento concluído com {resumo.contas_falha} falha(s). {resumo.pontos_totais} pontos obtidos.[/bold yellow]",
                border_style="yellow",
                box=box.DOUBLE
            ))
        console.print("\n")


    @staticmethod
    def _normalizar_acoes(acoes: Iterable[str]) -> List[str]:
        """
        Normaliza lista de ações.
        
        Args:
            acoes: Ações a normalizar
            
        Returns:
            List[str]: Ações normalizadas (lowercase, sem espaços)
        """
        return [acao.strip().lower() for acao in acoes if acao and acao.strip()]
