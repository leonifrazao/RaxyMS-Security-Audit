from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from raxy.domain.accounts import Conta
from raxy.interfaces.drivers import IBrowserDriver
from raxy.core.exceptions import (
    SessionException,
    ProxyRotationRequiredException,
    ProfileException,
    LoginException,
    InvalidCredentialsException,
    ElementNotFoundException,
    wrap_exception,
)
from raxy.interfaces.services import IProxyService, IMailTmService, ILoggingService, ISessionManager
from raxy.services.base_service import BaseService

# Importações dos módulos desacoplados
from raxy.core.session import (
    ProfileManager,
    BrowserLoginHandler,
    RequestExecutor
)




class SessionManagerService(BaseService, ISessionManager):
    """
    Serviço orquestrador de sessão.
    
    Responsabilidades:
    - Orquestra os componentes de sessão
    - Gerencia o ciclo de vida do driver
    - Coordena login e execução de templates
    - Mantém estado da sessão (cookies, UA, token)
    """


    def __init__(
        self,
        conta: Conta,
        proxy: dict | None = None,
        proxy_service: Optional[IProxyService] = None,
        mail_service: Optional[IMailTmService] = None,
        logger: Optional[ILoggingService] = None,
        event_bus: Optional[Any] = None,
    ) -> None:
        """
        Inicializa o serviço de sessão.
        
        Args:
            conta: Conta a ser utilizada
            proxy: Configuração de proxy
            proxy_service: Serviço de proxy para rotação
            mail_service: Serviço de email temporário
            logger: Serviço de logging
            event_bus: Event Bus para publicação de eventos
        """
        # Inicializa BaseService com logger contextualizado
        if not logger:
            from raxy.core.logging import get_logger
            logger = get_logger().com_contexto(
                conta=conta.email, 
                perfil=(conta.id_perfil or conta.email)
            )
        super().__init__(logger)
        
        # Dados da conta e proxy
        self.conta = conta
        self.proxy = proxy or {}
        
        # Event Bus para comunicação assíncrona E state management
        self._event_bus = event_bus
        self._session_start_time: Optional[float] = None
        self._state_ttl: int = 3600  # TTL padrão de 1 hora
        
        # Estado da sessão (apenas driver local, resto no Redis)
        self.driver: IBrowserDriver | None = None
        
        # Serviços externos
        self._proxy_service = proxy_service
        self._mail_service = mail_service
        
        # Componentes internos
        self._profile_manager = ProfileManager(
            conta=conta,
            mail_service=mail_service,
            logger=self.logger,
            event_bus=event_bus
        )
        self._request_executor = RequestExecutor(
            logger=self.logger,
            proxy=self.proxy,
            event_bus=event_bus
        )
    
    def _state_key(self, field: str) -> str:
        """
        Gera chave única para estado da sessão no Redis.
        
        Args:
            field: Nome do campo (cookies, user_agent, token)
            
        Returns:
            str: Chave formatada (ex: "session:user@email.com:cookies")
        """
        return f"session:{self.conta.email}:{field}"
    
    def _publish_event(self, event_name: str, data: dict[str, Any]) -> None:
        """
        Publica um evento no Event Bus se disponível.
        
        Args:
            event_name: Nome do evento (ex: "session.started")
            data: Dados do evento
        """
        if self._event_bus and hasattr(self._event_bus, 'publish'):
            try:
                self._event_bus.publish(event_name, data)
            except Exception:
                # Silenciosamente ignora erros de publicação
                pass
    
    # ========================================================================
    # ESTADO DISTRIBUÍDO - Properties com Redis Puro
    # ========================================================================
    
    @property
    def cookies(self) -> dict[str, str]:
        """
        Cookies da sessão (armazenados no Redis).
        
        Estado distribuído puro - sem fallback local.
        """
        if self._event_bus and hasattr(self._event_bus, 'get_state'):
            state = self._event_bus.get_state(self._state_key("cookies"), {})
            if state:
                self.logger.debug(
                    f"Cookies recuperados do Redis ({len(state)} cookies)",
                    source="redis",
                    key=self._state_key("cookies")
                )
            return state
        return {}
    
    @cookies.setter
    def cookies(self, value: dict[str, str]) -> None:
        """Define cookies (salva no Redis)."""
        if self._event_bus and hasattr(self._event_bus, 'set_state'):
            success = self._event_bus.set_state(
                self._state_key("cookies"), 
                value, 
                ttl=self._state_ttl
            )
            if success:
                self.logger.info(
                    f"Cookies salvos no Redis ({len(value)} cookies, TTL: {self._state_ttl}s)",
                    source="redis",
                    key=self._state_key("cookies")
                )
    
    @property
    def user_agent(self) -> str:
        """
        User-Agent da sessão (armazenado no Redis).
        
        Estado distribuído puro - sem fallback local.
        """
        if self._event_bus and hasattr(self._event_bus, 'get_state'):
            state = self._event_bus.get_state(self._state_key("user_agent"), "")
            if state:
                self.logger.debug(
                    f"User-Agent recuperado do Redis",
                    source="redis",
                    key=self._state_key("user_agent"),
                    ua_preview=state[:50] + "..." if len(state) > 50 else state
                )
            return state
        return ""
    
    @user_agent.setter
    def user_agent(self, value: str) -> None:
        """Define User-Agent (salva no Redis)."""
        if self._event_bus and hasattr(self._event_bus, 'set_state'):
            success = self._event_bus.set_state(
                self._state_key("user_agent"), 
                value, 
                ttl=self._state_ttl
            )
            if success:
                self.logger.info(
                    f"User-Agent salvo no Redis (TTL: {self._state_ttl}s)",
                    source="redis",
                    key=self._state_key("user_agent"),
                    ua_preview=value[:50] + "..." if len(value) > 50 else value
                )
    
    @property
    def token_antifalsificacao(self) -> str | None:
        """
        Token anti-falsificação (armazenado no Redis).
        
        Estado distribuído puro - sem fallback local.
        """
        if self._event_bus and hasattr(self._event_bus, 'get_state'):
            state = self._event_bus.get_state(self._state_key("token"), None)
            if state:
                self.logger.debug(
                    f"Token anti-falsificação recuperado do Redis",
                    source="redis",
                    key=self._state_key("token"),
                    token_preview=state[:20] + "..." if state and len(state) > 20 else state
                )
            return state
        return None
    
    @token_antifalsificacao.setter
    def token_antifalsificacao(self, value: str | None) -> None:
        """Define token (salva no Redis)."""
        if self._event_bus and hasattr(self._event_bus, 'set_state'):
            success = self._event_bus.set_state(
                self._state_key("token"), 
                value, 
                ttl=self._state_ttl
            )
            if success and value:
                self.logger.info(
                    f"Token anti-falsificação salvo no Redis (TTL: {self._state_ttl}s)",
                    source="redis",
                    key=self._state_key("token"),
                    token_preview=value[:20] + "..." if len(value) > 20 else value
                )

    def start(self) -> None:
        """
        Inicia a sessão com tratamento robusto de erros.
        
        Coordena:
        - Garantia de perfil via ProfileManager
        - Login via BrowserLoginHandler
        - Rotação de proxy se necessário
        - Atualização do estado da sessão
        """
        perfil_nome = self.conta.id_perfil or self.conta.email
        dados = {"proxy_id": self.proxy.get("id")}
        
        # 1. Garantir perfil e obter argumentos UA
        self.logger.info("Garantindo perfil e obtendo argumentos do User-Agent...")
        try:
            user_agent_args = self._profile_manager.garantir_perfil(perfil_nome)
            self.logger.sucesso(f"Perfil '{perfil_nome}' pronto. Argumentos UA obtidos.")
        except ProfileException:
            raise
        except Exception as e:
            raise wrap_exception(
                e, ProfileException,
                "Erro inesperado ao garantir perfil",
                perfil=perfil_nome, conta=self.conta.email
            )
        
        self.logger.info("Iniciando sessão/driver", perfil=perfil_nome, proxy_id=dados["proxy_id"])

        # Obtém configuração
        from raxy.core.config import get_config
        config = get_config()
        tentativas = config.session.max_login_attempts
        
        while tentativas > 0:
            try:
                # 2. Executar login via BrowserLoginHandler
                proxy_url = self.proxy.get("url") if self.proxy else None
                resultado = BrowserLoginHandler.executar_login(
                    profile=perfil_nome,
                    proxy=proxy_url,
                    data=dados,
                    browser_arguments=user_agent_args
                )
                
                # 3. Atualizar estado da sessão
                self._atualizar_estado_sessao(resultado)
                break
                
            except ProxyRotationRequiredException as e:
                self._tratar_rotacao_proxy(e, tentativas)
            except (LoginException, InvalidCredentialsException, ElementNotFoundException) as e:
                # Exceções de login não devem ser retentadas
                # Publica evento de erro
                self._publish_event("session.error", {
                    "session_id": f"session_{self.conta.email}",
                    "account_id": self.conta.email,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "is_recoverable": False,
                })
                raise
            except Exception as e:
                self.logger.erro(
                    f"Erro inesperado ao abrir driver: {e}",
                    erro=e,
                    tentativas_restantes=tentativas-1
                )
                # Publica evento de erro recuperável
                self._publish_event("session.error", {
                    "session_id": f"session_{self.conta.email}",
                    "account_id": self.conta.email,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "is_recoverable": True,
                })
                if tentativas == 1:
                    raise wrap_exception(
                        e, SessionException,
                        "Falha ao iniciar sessão após múltiplas tentativas",
                        conta=self.conta.email,
                        proxy_id=self.proxy.get("id")
                    )
            finally:
                tentativas -= 1
        
        if not self.driver:
            raise SessionException(
                f"Falha ao iniciar a sessão após {config.session.max_login_attempts} tentativas.",
                details={"conta": self.conta.email, "proxy_id": self.proxy.get("id")}
            )

        self.logger.sucesso("Sessão iniciada com sucesso.")
        
        # Registra tempo de início da sessão
        import time
        self._session_start_time = time.time()
        
        # Publica eventos de sucesso
        session_id = f"session_{self.conta.email}_{int(self._session_start_time)}"
        
        self._publish_event("session.started", {
            "session_id": session_id,
            "account_id": self.conta.email,
            "proxy_id": self.proxy.get("id"),
            "user_agent": self.user_agent,
        })
        
        self._publish_event("account.logged_in", {
            "account_id": self.conta.email,
            "email": self.conta.email,
            "profile_id": self.conta.id_perfil or self.conta.email,
            "proxy_id": self.proxy.get("id"),
            "market": None,  # Pode ser extraído futuramente
        })
    
    def _atualizar_estado_sessao(self, resultado: dict[str, Any]) -> None:
        """
        Atualiza o estado da sessão com os dados do login.
        
        Args:
            resultado: Dicionário com dados do login
        """
        self.driver = resultado["driver"]
        self.cookies = resultado["cookies"]
        self.user_agent = resultado["ua"]
        self.token_antifalsificacao = resultado["token"]
        
        # Atualiza o RequestExecutor com os novos dados
        self._request_executor.atualizar_sessao(
            cookies=self.cookies,
            user_agent=self.user_agent,
            token_antifalsificacao=self.token_antifalsificacao
        )
    
    def _tratar_rotacao_proxy(self, e: ProxyRotationRequiredException, tentativas: int) -> None:
        """
        Trata a rotação de proxy quando necessário.
        
        Args:
            e: Exceção de rotação
            tentativas: Número de tentativas restantes
        """
        self.logger.aviso(f"Exceção de rotação: {e}. Tentando próxima proxy.")
        
        if self._proxy_service:
            try:
                self._proxy_service.rotate_proxy(self.proxy.get("id"))
            except Exception as rotate_err:
                self.logger.erro(f"Erro ao rotacionar proxy: {rotate_err}")
                if tentativas == 1:
                    raise wrap_exception(
                        rotate_err, ProxyRotationRequiredException,
                        "Falha ao rotacionar proxy",
                        proxy_id=self.proxy.get("id"),
                        attempts_left=tentativas
                    )
        else:
            self.logger.erro("ProxyRotationRequiredException, mas _proxy_service ausente para rotação.")
            raise e
    
    def execute_template(
        self,
        template_path_or_dict: str | Path | Mapping[str, Any],
        *,
        placeholders: Mapping[str, Any] | None = None,
        use_ua: bool = True,
        use_cookies: bool = True,
        bypass_request_token: bool = True,
    ) -> Any:
        """
        Executa um template de requisição.
        
        Delega para o RequestExecutor após verificar estado da sessão.
        
        Args:
            template_path_or_dict: Caminho para o template ou dicionário
            placeholders: Valores para substituir no template
            use_ua: Se deve usar o User-Agent da sessão
            use_cookies: Se deve usar os cookies da sessão
            bypass_request_token: Se deve adicionar token de verificação
            
        Returns:
            Resposta da requisição
            
        Raises:
            SessionException: Se sessão não estiver iniciada
        """
        if not self.driver:
            raise SessionException(
                "Sessão não iniciada",
                details={"conta": self.conta.email}
            )
        
        return self._request_executor.executar_template(
            template_path_or_dict,
            placeholders=placeholders,
            use_ua=use_ua,
            use_cookies=use_cookies,
            bypass_request_token=bypass_request_token
        )
    
    def close(self) -> None:
        """
        Fecha a sessão e limpa recursos.
        """
        # Calcula duração da sessão
        import time
        duration_seconds = 0.0
        if self._session_start_time:
            duration_seconds = time.time() - self._session_start_time
        
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.erro(f"Erro ao fechar driver: {e}")
            finally:
                self.driver = None
                
                # Limpa estado distribuído (Redis)
                if self._event_bus and hasattr(self._event_bus, 'delete_state'):
                    deleted_count = 0
                    if self._event_bus.delete_state(self._state_key("cookies")):
                        deleted_count += 1
                    if self._event_bus.delete_state(self._state_key("user_agent")):
                        deleted_count += 1
                    if self._event_bus.delete_state(self._state_key("token")):
                        deleted_count += 1
                    
                    if deleted_count > 0:
                        self.logger.info(
                            f"Estado da sessão removido do Redis ({deleted_count} chaves)",
                            source="redis",
                            conta=self.conta.email
                        )
        
        # Publica evento de sessão encerrada
        if self._session_start_time:
            session_id = f"session_{self.conta.email}_{int(self._session_start_time)}"
            self._publish_event("session.ended", {
                "session_id": session_id,
                "account_id": self.conta.email,
                "duration_seconds": duration_seconds,
                "reason": "Normal closure",
            })
            
            self._publish_event("account.logged_out", {
                "account_id": self.conta.email,
                "email": self.conta.email,
                "reason": "Session closed",
            })
        
        self.logger.debug("Sessão fechada")
    
    def __repr__(self) -> str:
        """Representação string do serviço."""
        status = "ativa" if self.driver else "inativa"
        return f"SessionManagerService(conta={self.conta.email}, sessão={status})"