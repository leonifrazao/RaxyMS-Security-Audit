from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from raxy.core.domain.accounts import Conta
from raxy.core.domain.proxy import Proxy
from raxy.core.interfaces import SessionStateRepository
from raxy.core.exceptions import (
    SessionException,
    ProxyRotationRequiredException,
    LoginException,
    InvalidCredentialsException,
    wrap_exception,
    ProfileException,
)
from raxy.core.services.base_service import BaseService
from raxy.core.services.session import (
    ProfileManager,
    BrowserLoginHandler,
    RequestExecutor
)


class SessionManagerService(BaseService):
    """
    Serviço orquestrador de sessão.
    
    Responsabilidades:
    - Orquestra os componentes de sessão
    - Gerencia o ciclo de vida do driver
    - Coordena login e execução
    - Usa Repository Pattern para persistência de estado
    """

    def __init__(
        self,
        conta: Conta,
        state_repository: SessionStateRepository,  # Injeção de dependência obrigatória
        proxy: Proxy | dict | None = None,
        proxy_service: Optional[Any] = None,
        mail_service: Optional[Any] = None,
        logger: Optional[Any] = None,
        event_bus: Optional[Any] = None,
    ) -> None:
        """
        Inicializa o serviço de sessão.

        Args:
            conta: Entidade da conta.
            state_repository: Repositório para cookies/tokens.
            proxy: Proxy ou dict.
            proxy_service: Serviço de rotação.
            mail_service: Serviço de email.
            logger: Opcional.
            event_bus: Opcional (apenas para eventos, não state).
        """
        # Inicializa BaseService com logger contextualizado
        if not logger:
            from raxy.infrastructure.logging import get_logger
            logger = get_logger().com_contexto(
                conta=conta.email, 
                perfil=(conta.id_perfil or conta.email)
            )
        super().__init__(logger)
        
        self.conta = conta
        self.state_repository = state_repository
        
        # Normaliza proxy
        if isinstance(proxy, dict):
            self.proxy = Proxy(
                id=proxy.get("id", ""),
                url=proxy.get("url", ""),
                type=proxy.get("type", "http"),
                country=proxy.get("country"),
            )
        else:
            self.proxy = proxy or Proxy(id="", url="")

        self._event_bus = event_bus
        self._session_start_time: Optional[float] = None
        self.driver: Any | None = None
        
        self._proxy_service = proxy_service
        self._mail_service = mail_service
        
        # Inicializa componentes internos com dependências injetadas
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

    # ========================================================================
    # Gerenciamento de Estado (Via Repository)
    # ========================================================================
    
    @property
    def cookies(self) -> dict[str, str]:
        """Recupera cookies do repositório."""
        return self.state_repository.get_state(self.conta.email, "cookies", {})
    
    @cookies.setter
    def cookies(self, value: dict[str, str]) -> None:
        """Salva cookies no repositório."""
        self.state_repository.save_state(self.conta.email, "cookies", value)
    
    @property
    def user_agent(self) -> str:
        """Recupera User-Agent do repositório."""
        return self.state_repository.get_state(self.conta.email, "user_agent", "")
    
    @user_agent.setter
    def user_agent(self, value: str) -> None:
        """Salva User-Agent no repositório."""
        self.state_repository.save_state(self.conta.email, "user_agent", value)
    
    @property
    def token_antifalsificacao(self) -> str | None:
        """Recupera token do repositório."""
        return self.state_repository.get_state(self.conta.email, "token", None)
    
    @token_antifalsificacao.setter
    def token_antifalsificacao(self, value: str | None) -> None:
        """Salva token no repositório."""
        self.state_repository.save_state(self.conta.email, "token", value)

    # ========================================================================
    # Ciclo de Vida da Sessão
    # ========================================================================

    def start(self) -> None:
        """Inicia a sessão, driver e restaura estado."""
        perfil_nome = self.conta.id_perfil or self.conta.email
        
        self.logger.info("Preparando sessão...")
        
        try:
            # 1. Preparar Perfil
            ua_args = self._profile_manager.garantir_perfil(perfil_nome)
            
            # 2. Iniciar Driver (Login)
            self._realizar_login(perfil_nome, ua_args)
            
            # 3. Notificar sucesso
            self._notificar_inicio_sessao()
            
        except Exception as e:
            # Propaga exceções já tratadas ou envolve as desconhecidas
            if isinstance(e, (SessionException, ProfileException)):
                raise
            raise wrap_exception(e, SessionException, "Falha crítica ao iniciar sessão")

    def _realizar_login(self, perfil: str, ua_args: list[str]) -> None:
        """Lógica de retry para login."""
        from raxy.config import get_config
        max_attempts = get_config().session.max_login_attempts
        
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                proxy_url = self.proxy.url if self.proxy.is_valid else None
                
                # Executa o login usando o Handler especializado
                resultado = BrowserLoginHandler.executar_login(
                    profile=perfil,
                    proxy=proxy_url,
                    data={"proxy_id": self.proxy.id},
                    browser_arguments=ua_args
                )
                
                # Salva estado obtido no login
                self.driver = resultado["driver"]
                self.cookies = resultado["cookies"]
                self.user_agent = resultado["ua"]
                self.token_antifalsificacao = resultado["token"]
                
                # Sincroniza executor
                self._request_executor.atualizar_sessao(
                    cookies=self.cookies,
                    user_agent=self.user_agent,
                    token_antifalsificacao=self.token_antifalsificacao
                )
                return
                
            except ProxyRotationRequiredException:
                self.logger.aviso("Rotação de proxy solicitada durante login.")
                if self._proxy_service:
                    try:
                        self._proxy_service.rotate_proxy(self.proxy.id)
                    except Exception as e:
                         # Se falhar rotação, não há muito o que fazer
                         self.logger.erro(f"Falha ao rotacionar proxy: {e}")
                else:
                    raise
            except (LoginException, InvalidCredentialsException):
                # Erros fatais de credenciais não devem ter retry
                self.logger.erro("Credenciais inválidas ou erro fatal no login.")
                raise
            except Exception as e:
                self.logger.erro(f"Tentativa {attempt}/{max_attempts} falhou: {e}")
                if attempt >= max_attempts:
                    raise SessionException(f"Falha no login após {max_attempts} tentativas.") from e

    def _notificar_inicio_sessao(self) -> None:
        """Publica eventos de início de sessão."""
        import time
        self._session_start_time = time.time()
        
        if self._event_bus:
            session_id = f"sess_{self.conta.email}_{int(self._session_start_time)}"
            self._event_bus.publish("session.started", {
                "session_id": session_id,
                "email": self.conta.email,
                "proxy_id": self.proxy.id
            })

    def execute_template(
        self,
        template: str | Path | Mapping[str, Any],
        **kwargs
    ) -> Any:
        """Executa um template via RequestExecutor."""
        if not self.driver:
            raise SessionException("Sessão não iniciada")
            
        return self._request_executor.executar_template(template, **kwargs)

    def close(self) -> None:
        """Encerra a sessão e limpa recursos."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None
        
        # Limpa estado se necessário (opcional, dependendo da regra de negócio)
        # self.state_repository.clear_state(self.conta.email)
        
        self.logger.debug("Sessão encerrada.")
