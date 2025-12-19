"""
Serviço de execução em lote refatorado.

Gerencia a execução paralela de tarefas para múltiplas contas
com suporte a proxies, logging estruturado e tratamento robusto de erros.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from raxy.domain import Conta, InfraServices
from raxy.core.session_manager_service import SessionManagerService
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
from raxy.interfaces.services import IExecutorEmLoteService, ILoggingService
from .base_service import BaseService


@dataclass
class EtapaResult:
    """Resultado de uma etapa individual."""
    nome: str
    sucesso: bool
    erro: Optional[str] = None
    dados: Optional[Dict[str, Any]] = None


@dataclass
class ContaResult:
    """Resultado detalhado do processamento de uma conta."""
    email: str
    sucesso_geral: bool
    pontos_iniciais: int = 0
    pontos_finais: int = 0
    pontos_ganhos: int = 0
    etapas: List[EtapaResult] = field(default_factory=list)
    erro_fatal: Optional[str] = None
    proxy_usado: Optional[str] = None
    
    def adicionar_etapa(self, nome: str, sucesso: bool, erro: Optional[str] = None, dados: Optional[Dict[str, Any]] = None) -> None:
        """Adiciona resultado de uma etapa."""
        self.etapas.append(EtapaResult(
            nome=nome,
            sucesso=sucesso,
            erro=erro,
            dados=dados
        ))
    
    def get_resumo(self) -> Dict[str, Any]:
        """Retorna resumo do resultado."""
        etapas_ok = sum(1 for e in self.etapas if e.sucesso)
        etapas_falha = len(self.etapas) - etapas_ok
        
        return {
            "email": self.email,
            "sucesso": self.sucesso_geral,
            "pontos_iniciais": self.pontos_iniciais,
            "pontos_finais": self.pontos_finais,
            "pontos_ganhos": self.pontos_ganhos,
            "etapas_ok": etapas_ok,
            "etapas_falha": etapas_falha,
            "total_etapas": len(self.etapas),
            "erro_fatal": self.erro_fatal,
            "proxy": self.proxy_usado,
            "detalhes_etapas": [
                {
                    "nome": e.nome,
                    "sucesso": e.sucesso,
                    "erro": e.erro
                }
                for e in self.etapas
            ]
        }


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
    
    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo das estatísticas."""
        return {
            "total": self.total_contas,
            "sucesso": self.contas_sucesso,
            "falha": self.contas_falha,
            "pontos_totais": self.pontos_totais,
            "taxa_sucesso": f"{(self.contas_sucesso/self.total_contas*100):.1f}%" if self.total_contas > 0 else "0%",
            "resultados_detalhados": [r.get_resumo() for r in self.resultados_contas]
        }


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
        debug: bool = False,
        event_bus=None
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
        self.debug = debug
        
        # Event Bus (opcional)
        self._event_bus = event_bus
    
    @debug_log(log_args=False, log_result=False, log_duration=True)
    def process(
        self,
        conta: Conta,
        acoes: Sequence[str],
        proxy: Optional[Dict[str, str]] = None
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
            proxy_usado=proxy.get("id") if proxy else None
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
            
            # Etapa 1: Login/Criar sessão
            try:
                sessao = self._criar_sessao(conta, proxy, logger)
                resultado.adicionar_etapa("login", True, dados={"email": conta.email})
            except (InvalidCredentialsException, LoginException) as e:
                erro_msg = f"Credenciais inválidas: {str(e)}"
                resultado.adicionar_etapa("login", False, erro=erro_msg)
                resultado.erro_fatal = f"Falha no login: {str(e)}"
                logger.erro(f"Falha de autenticação", error=erro_msg)
                return resultado
            except SessionException as e:
                erro_msg = f"Erro de sessão: {str(e)}"
                resultado.adicionar_etapa("login", False, erro=erro_msg)
                resultado.erro_fatal = f"Falha na sessão: {str(e)}"
                logger.erro(f"Falha na sessão", error=erro_msg)
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
                
                sucesso_acao, erro_acao = self._executar_acao_com_resultado(acao, sessao, logger)
                resultado.adicionar_etapa(acao, sucesso_acao, erro=erro_acao)
            
            # Etapa 4: Obter pontos finais
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
            if resultado.pontos_finais > 0:
                try:
                    self._salvar_no_banco(conta.email, resultado.pontos_finais, logger)
                    resultado.adicionar_etapa("salvar_banco", True)
                except Exception as e:
                    resultado.adicionar_etapa("salvar_banco", False, erro=str(e))
            
            # Marca como sucesso geral
            resultado.sucesso_geral = True
            return resultado
            
        except Exception as e:
            resultado.erro_fatal = f"Erro crítico: {str(e)}"
            logger.erro(f"Erro crítico no processamento", error=str(e), exception=e)
            return resultado
    
    def _criar_sessao(
        self,
        conta: Conta,
        proxy: Optional[Dict[str, str]],
        logger: ILoggingService
    ) -> SessionManagerService:
        """Cria e inicializa sessão."""
        sessao = SessionManagerService(
            conta=conta,
            proxy=proxy or {},
            proxy_service=self.proxy_service,
            mail_service=self.mail_service,
            logger=logger,
            event_bus=getattr(self, '_event_bus', None)
        )
        sessao.start()
        return sessao
    
    def _obter_pontos(self, sessao: SessionManagerService, logger: ILoggingService) -> int:
        """Obtém pontos da conta."""
        try:
            pontos = self.rewards_service.obter_pontos(sessao)
            return pontos
        except Exception as e:
            return 0
    
    def _executar_acao_com_resultado(
        self,
        acao: str,
        sessao: SessionManagerService,
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
                self.bing_search_service.get_all(sessao, "Brasil")
                return True, None
                
            else:
                return False, f"Ação desconhecida: {acao}"
                
        except Exception as e:
            erro_msg = f"{type(e).__name__}: {str(e)}"
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
        logger: Optional[ILoggingService] = None,
        event_bus=None
    ) -> None:
        """
        Inicializa o executor.
        
        Args:
            services: Serviços de infraestrutura
            config: Configuração do executor
            proxy_config: Configuração de proxy
            logger: Serviço de logging
            event_bus: Event Bus para publicação de eventos
        """
        super().__init__(logger)
        self._config = config or ExecutorConfig()
        self._proxy_config = proxy_config or ProxyConfig()
        self._services = services
        
        # Event Bus
        self._event_bus = event_bus
        
        # Injeção de dependências específicas (melhor desacoplamento)
        self._processor = AccountProcessor(
            rewards_service=services.rewards_data,
            bing_search_service=services.bing_search,
            flyout_service=services.bing_flyout_service,
            proxy_service=services.proxy_manager,
            mail_service=services.mail_tm_service,
            db_repository=services.db_repository,
            logger=self.logger,
            debug=self._config.debug,
            event_bus=event_bus
        )
        self._stats = ExecutionStats()
    
    def _publish_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Publica evento no Event Bus se disponível."""
        if self._event_bus and hasattr(self._event_bus, 'publish'):
            try:
                self._event_bus.publish(event_name, data)
            except Exception:
                pass

    @debug_log(log_args=False, log_result=False, log_duration=True)
    def executar(
        self,
        acoes: Optional[Iterable[str]] = None,
        contas: Optional[Sequence[Conta]] = None
    ) -> Dict[str, Any]:
        """
        Executa o processamento em lote.
        
        Args:
            acoes: Ações a executar (usa config se None)
            contas: Contas a processar (busca do repositório se None)
            
        Returns:
            Dict[str, Any]: Estatísticas da execução
            
        Raises:
            ExecutionException: Se erro crítico na execução
        """
        # Inicia Event Bus se disponível
        event_bus_iniciado = False
        if self._event_bus:
            try:
                if not getattr(self._event_bus, '_running', False):
                    self.logger.info("Iniciando Event Bus (Redis) para estado distribuído...")
                    self._event_bus.start()
                    event_bus_iniciado = True
                    self.logger.sucesso("Event Bus iniciado com sucesso")
            except Exception as e:
                self.logger.aviso(f"Não foi possível iniciar Event Bus: {e}. Continuando sem estado distribuído.")
        
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
                
                # Prepara proxies se necessário
                proxies = self._preparar_proxies() if self._proxy_config.enabled else []
                
                # Executa processamento paralelo
                self._processar_paralelo(contas_proc, acoes_norm, proxies)
                
                # Retorna estatísticas
                resumo = self._stats.get_summary()
                self._log_resumo(resumo)
                
                # Publica evento de execução completa
                self._publish_event("executor.batch_completed", {
                    "total_accounts": resumo["total"],
                    "success_count": resumo["sucesso"],
                    "failed_count": resumo["falha"],
                    "total_points": resumo["pontos_totais"],
                    "success_rate": resumo["taxa_sucesso"],
                    "timestamp": __import__('time').time(),
                })
                
                return resumo
        
        finally:
            # Para Event Bus (Redis) se foi iniciado por este executor
            if event_bus_iniciado and self._event_bus and hasattr(self._event_bus, 'stop'):
                try:
                    self.logger.info("Parando Event Bus (Redis)...")
                    self._event_bus.stop()
                    self.logger.sucesso("Event Bus parado com sucesso")
                except Exception as e:
                    self.logger.aviso(f"Erro ao parar Event Bus: {e}")
    
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
            List[Dict[str, str]]: Lista de proxies
        """
        try:
            proxies = self._services.proxy_manager.start(
                auto_test=self._proxy_config.auto_test,
                threads=self._config.max_workers,
                find_first=20
            )
            return proxies
        except Exception as e:
            return []
    
    def _processar_paralelo(
        self,
        contas: List[Conta],
        acoes: List[str],
        proxies: List[Dict[str, str]]
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
                    
                    # Publica evento de conta processada
                    if resultado.sucesso_geral:
                        self._publish_event("executor.account_completed", {
                            "account_id": conta.email,
                            "points_earned": resultado.pontos_ganhos,
                            "points_total": resultado.pontos_finais,
                            "tasks_completed": sum(1 for e in resultado.etapas if e.sucesso),
                            "timestamp": __import__('time').time(),
                        })
                        
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
        proxy: Optional[Dict[str, str]]
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
                proxy_usado=proxy.get("id") if proxy else None
            )
    
    def _log_resumo(self, resumo: Dict[str, Any]) -> None:
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
        
        tabela_geral.add_row("Total de Contas", str(resumo["total"]))
        tabela_geral.add_row("Sucessos", f"[green]{resumo['sucesso']}[/green]")
        tabela_geral.add_row("Falhas", f"[red]{resumo['falha']}[/red]")
        tabela_geral.add_row("Pontos Totais", f"[yellow]{resumo['pontos_totais']}[/yellow]")
        tabela_geral.add_row("Taxa de Sucesso", f"[bold]{resumo['taxa_sucesso']}[/bold]")
        
        console.print("\n")
        console.print(tabela_geral)
        
        # Tabela detalhada de contas
        if resumo.get("resultados_detalhados"):
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
            
            for resultado in resumo["resultados_detalhados"]:
                status_icon = "✅" if resultado["sucesso"] else "❌"
                ganhos_str = f"+{resultado['pontos_ganhos']}" if resultado['pontos_ganhos'] > 0 else str(resultado['pontos_ganhos'])
                
                row_data = [
                    resultado["email"],
                    status_icon,
                    str(resultado["pontos_finais"]),
                    ganhos_str,
                    str(resultado["etapas_ok"]),
                    str(resultado["etapas_falha"])
                ]
                
                if self._config.debug:
                    erro = resultado.get("erro_fatal", "-")
                    if erro and len(erro) > 40:
                        erro = erro[:37] + "..."
                    row_data.append(erro or "-")
                
                tabela_contas.add_row(*row_data)
            
            console.print(tabela_contas)
        
        # Mensagem final
        console.print("\n")
        if resumo["falha"] == 0:
            console.print(Panel(
                f"[bold green]✅ Processamento concluído com sucesso! {resumo['pontos_totais']} pontos obtidos.[/bold green]",
                border_style="green",
                box=box.DOUBLE
            ))
        else:
            console.print(Panel(
                f"[bold yellow]⚠️ Processamento concluído com {resumo['falha']} falha(s). {resumo['pontos_totais']} pontos obtidos.[/bold yellow]",
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
