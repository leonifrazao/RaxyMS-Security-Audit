from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional
import time

from raxy.domain.proxy import ProxyItem
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

# Importações locais do pacote infrastructure.session
from .profile_manager import ProfileManager
from .browser_login_handler import BrowserLoginHandler
from .request_executor import RequestExecutor


class SessionManager(BaseService, ISessionManager):
    """
    Serviço orquestrador de sessão.
    
    Responsabilidades:
    - Estado da sessão (cookies, UA, token)
    - Coordena login (refresh de sessão)
    - Executa templates de requisição via RequestExecutor
    """

    def __init__(
        self,
        conta: Conta,
        proxy: ProxyItem | None = None,
        proxy_service: Optional[IProxyService] = None,
        mail_service: Optional[IMailTmService] = None,
        logger: Optional[ILoggingService] = None,
    ) -> None:
        """
        Inicializa o serviço de sessão.
        
        Args:
            conta: Conta a ser utilizada
            proxy: Item de proxy (ProxyItem domain object)
            proxy_service: Serviço de proxy para rotação
            mail_service: Serviço de email temporário
            logger: Serviço de logging
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
        self.proxy = proxy
        
        # Estado local da sessão
        self._cookies: dict[str, str] = {}
        self._user_agent: str = ""
        self._token_antifalsificacao: Optional[str] = None
        self._session_start_time: Optional[float] = None
        
        # Serviços externos
        self._proxy_service = proxy_service
        self._mail_service = mail_service
        
        # Componentes internos
        self._profile_manager = ProfileManager(
            conta=conta,
            mail_service=mail_service,
            logger=self.logger
        )
        # RequestExecutor agora é stateless e só precisa do logger
        self._request_executor = RequestExecutor(
            logger=self.logger
        )
    
    @property
    def cookies(self) -> dict[str, str]:
        """Cookies da sessão."""
        return self._cookies
    
    @cookies.setter
    def cookies(self, value: dict[str, str]) -> None:
        """Define cookies."""
        self._cookies = value or {}
    
    @property
    def user_agent(self) -> str:
        """User-Agent da sessão."""
        return self._user_agent
    
    @user_agent.setter
    def user_agent(self, value: str) -> None:
        """Define User-Agent."""
        self._user_agent = value or ""
    
    @property
    def token_antifalsificacao(self) -> str | None:
        """Token anti-falsificação."""
        return self._token_antifalsificacao
    
    @token_antifalsificacao.setter
    def token_antifalsificacao(self, value: str | None) -> None:
        """Define token."""
        self._token_antifalsificacao = value

    def start(self) -> None:
        """
        Atualiza a sessão realizando login (Refresh Session).
        
        - Garante perfil
        - Abre driver isolado
        - Realiza login
        - Coleta cookies/token
        - Fecha driver
        """
        self.refresh_session()

    def refresh_session(self) -> None:
        """
        Executa fluxo de login para atualizar credenciais da sessão.
        """
        perfil_nome = self.conta.id_perfil or self.conta.email
        dados = {"proxy_id": self.proxy.tag if self.proxy else None}
        
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
        
        self.logger.info("Iniciando login (driver isolado)", perfil=perfil_nome, proxy_id=dados["proxy_id"])

        # Obtém configuração
        from raxy.core.config import get_config
        config = get_config()
        tentativas = config.session.max_login_attempts
        
        sucesso = False
        while tentativas > 0:
            driver_temp = None
            try:
                # 2. Executar login via BrowserLoginHandler
                proxy_url = self.proxy.uri if self.proxy else None
                resultado = BrowserLoginHandler.executar_login(
                    profile=perfil_nome,
                    proxy=proxy_url,
                    data=dados,
                    browser_arguments=user_agent_args
                )
                
                # 3. Atualizar estado da sessão
                self._atualizar_estado_sessao(resultado)
                
                # Garante fechamento do driver retornado
                driver_temp = resultado.get("driver")
                if driver_temp:
                    try:
                        if hasattr(driver_temp, "quit"):
                            driver_temp.quit()
                        elif hasattr(driver_temp, "driver") and hasattr(driver_temp.driver, "quit"):
                            driver_temp.driver.quit()
                    except Exception:
                        pass
                
                sucesso = True
                break
                
            except ProxyRotationRequiredException as e:
                self._tratar_rotacao_proxy(e, tentativas)
            except (LoginException, InvalidCredentialsException, ElementNotFoundException) as e:
                # Exceções de login não devem ser retentadas
                self.logger.erro(f"Erro irrecuperável de login: {e}")
                raise
            except Exception as e:
                self.logger.erro(
                    f"Erro inesperado no login: {e}",
                    erro=e,
                    tentativas_restantes=tentativas-1
                )
                if tentativas == 1:
                    raise wrap_exception(
                        e, SessionException,
                        "Falha ao iniciar sessão após múltiplas tentativas",
                        conta=self.conta.email,
                        proxy_id=(self.proxy.tag if self.proxy else None)
                    )
            finally:
                tentativas -= 1
        
        if sucesso:
            self.logger.sucesso("Sessão atualizada com sucesso.")
            self._session_start_time = time.time()
        else:
             raise SessionException(
                f"Falha ao atualizar sessão após {config.session.max_login_attempts} tentativas.",
                details={"conta": self.conta.email}
            )
    
    def _atualizar_estado_sessao(self, resultado: dict[str, Any]) -> None:
        """
        Atualiza o estado da sessão com os dados do login.
        
        Args:
            resultado: Dicionário com dados do login
        """
        self.cookies = resultado.get("cookies", {})
        self.user_agent = resultado.get("ua", "")
        self.token_antifalsificacao = resultado.get("token")
    
    def _tratar_rotacao_proxy(self, e: ProxyRotationRequiredException, tentativas: int) -> None:
        """
        Trata a rotação de proxy quando necessário.
        """
        self.logger.aviso(f"Exceção de rotação: {e}. Tentando próxima proxy.")
        
        if self._proxy_service:
            try:
                self._proxy_service.rotate_proxy(self.proxy.tag if self.proxy else None)
            except Exception as rotate_err:
                self.logger.erro(f"Erro ao rotacionar proxy: {rotate_err}")
                if tentativas == 1:
                    raise wrap_exception(
                        rotate_err, ProxyRotationRequiredException,
                        "Falha ao rotacionar proxy",
                        proxy_id=(self.proxy.tag if self.proxy else None),
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
        mobile: bool = False,
    ) -> Any:
        """
        Executa um template de requisição.
        
        Args:
            template_path_or_dict: Caminho para o template ou dicionário
            placeholders: Valores para substituir no template
            use_ua: Se deve usar o User-Agent da sessão
            use_cookies: Se deve usar os cookies da sessão
            bypass_request_token: Se deve adicionar token de verificação
            mobile: Se True, tenta usar User-Agent mobile (override)
            
        Returns:
            Resposta da requisição
            
        Raises:
            SessionException: Se sessão não estiver iniciada (sem cookies)
        """
        if not self.cookies:
            raise SessionException(
                "Sessão sem cookies (execute start/refresh_session primeiro)",
                details={"conta": self.conta.email}
            )
        
        self.logger.debug(f"Executando template: {template_path_or_dict.name if isinstance(template_path_or_dict, Path) else 'dict'} (Mobile={mobile})")
        
        # Determina UA a ser usado
        ua_to_use = self.user_agent
        if mobile:
            perfil = self.conta.id_perfil or self.conta.email
            try:
                ua_to_use = self._profile_manager.garantir_mobile_ua(perfil)
                self.logger.debug("Usando User-Agent Mobile Override")
            except Exception as e:
                self.logger.aviso(f"Falha ao obter UA Mobile, usando padrão: {e}")

        
        return self._request_executor.executar_template(
            template_path_or_dict,
            cookies=self.cookies,
            user_agent=ua_to_use,
            token_antifalsificacao=self.token_antifalsificacao,
            proxy=self.proxy,
            placeholders=placeholders,
            use_ua=use_ua,
            use_cookies=use_cookies,
            bypass_request_token=bypass_request_token
        )
    
    def close(self) -> None:
        """
        Limpa recursos da sessão.
        """
        # Calcula duração da sessão (meramente informativo agora)
        duration_seconds = 0.0
        if self._session_start_time:
            duration_seconds = time.time() - self._session_start_time
            
        self.logger.debug(f"Sessão finalizada (Duração: {duration_seconds:.2f}s)")
        
        # Limpa estado local
        self._cookies = {}
        self._token_antifalsificacao = None
    
    def __repr__(self) -> str:
        """Representação string do serviço."""
        status = "ativa" if self.cookies else "inativa"
        return f"SessionManager(conta={self.conta.email}, status={status})"