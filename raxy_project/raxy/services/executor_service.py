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

from raxy.domain import Conta
from raxy.domain.proxy import Proxy
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
from .base_service import BaseService


from raxy.domain.execution import ContaResult, EtapaResult


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
        logger: Any,
        debug: bool = False
    ):
        """
        Inicializa o processador com dependências específicas.
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
    
    @debug_log(log_args=False, log_result=False, log_duration=True)
    def process(
        self,
        conta: Conta,
        acoes: Sequence[str],
        proxy: Optional[Proxy] = None
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
            proxy_usado=proxy.id if proxy else None
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
        proxy: Optional[Proxy],
        logger: Any
    ) -> SessionManagerService:
        """Cria e inicializa sessão."""
        sessao = SessionManagerService(
            conta=conta,
            proxy=proxy,
            proxy_service=self.proxy_service,
            mail_service=self.mail_service,
            logger=logger
        )
        sessao.start()
        return sessao
    
    def _obter_pontos(self, sessao: SessionManagerService, logger: Any) -> int:
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
        logger: Any
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
        logger: Any
    ) -> None:
        """Salva registro no banco de dados."""
        try:
            if self.db_repository:
                self.db_repository.adicionar_registro_farm(email, pontos)
        except Exception as e:
            pass


class ExecutorEmLote(BaseService):
    """
    Executor de fluxos em lote com processamento paralelo.
    
    Gerencia a execução de tarefas para múltiplas contas
    com suporte a proxies e tratamento robusto de erros.
    """
    
    def __init__(
        self,
        rewards_service: Any,
        bing_search_service: Any,
        bing_flyout_service: Any,
        proxy_manager: Any,
        mail_tm_service: Any,
        conta_repository: Any,
        db_repository: Any,
        config: Optional[ExecutorConfig] = None,
        proxy_config: Optional[ProxyConfig] = None,
        logger: Optional[Any] = None
    ) -> None:
        """
        Inicializa o executor.
        
        Args:
            rewards_service: Serviço de rewards
            bing_search_service: Serviço de busca
            bing_flyout_service: Serviço de flyout
            proxy_manager: Gerenciador de proxies
            mail_tm_service: Serviço de email
            conta_repository: Repositório de contas
            db_repository: Repositório de banco de dados
            config: Configuração do executor
            proxy_config: Configuração de proxy
            logger: Serviço de logging
        """
        super().__init__(logger)
        self._config = config or ExecutorConfig()
        self._proxy_config = proxy_config or ProxyConfig()
        
        # Dependências diretas
        self.rewards_service = rewards_service
        self.bing_search_service = bing_search_service
        self.bing_flyout_service = bing_flyout_service
        self.proxy_manager = proxy_manager
        self.mail_tm_service = mail_tm_service
        self.conta_repository = conta_repository
        self.db_repository = db_repository
        
        # Injeção de dependências específicas (melhor desacoplamento)
        self._processor = AccountProcessor(
            rewards_service=rewards_service,
            bing_search_service=bing_search_service,
            flyout_service=bing_flyout_service,
            proxy_service=proxy_manager,
            mail_service=mail_tm_service,
            db_repository=db_repository,
            logger=self.logger,
            debug=self._config.debug
        )
        self._stats = ExecutionStats()
    


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
                
                if self._proxy_config.enabled and not proxies:
                    raise ExecutionException("Nenhum proxy disponível para execução. Verifique a configuração e a disponibilidade dos proxies.")

                # Executa processamento paralelo
                self._processar_paralelo(contas_proc, acoes_norm, proxies)
                
                # Retorna estatísticas
                resumo = self._stats.get_summary()
                self._log_resumo(resumo)
                

                
                return resumo
        
        except Exception as e:
            self.logger.erro(f"Erro na execução em lote: {e}")
            raise wrap_exception(e, ExecutionException, "Erro crítico na execução em lote")
        

    
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
            
            return self.conta_repository.listar()
        except Exception as e:
            self.handle_error(e, {"context": "carregamento de contas"})
    
    def _preparar_proxies(self) -> List[Proxy]:
        """
        Prepara proxies para uso.
        
        Returns:
            List[Proxy]: Lista de proxies
        """
        try:
            proxies_dicts = self.proxy_manager.start(
                auto_test=self._proxy_config.auto_test,
                threads=self._config.max_workers,
                country=self._proxy_config.country,
                find_first=20
            )
            
            # Converte para objetos Proxy
            return [
                Proxy(
                    id=p.get("id", ""),
                    url=p.get("url", ""),
                    type=p.get("type", "http"),
                    country=p.get("country"),
                    city=p.get("city")
                )
                for p in proxies_dicts
            ]
        except Exception as e:
            self.logger.erro(f"Erro ao preparar proxies: {e}")
            raise
    
    def _processar_paralelo(
        self,
        contas: List[Conta],
        acoes: List[str],
        proxies: List[Proxy]
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
        proxy: Optional[Proxy]
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
                proxy_usado=proxy.id if proxy else None
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
