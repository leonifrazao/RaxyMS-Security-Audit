from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional
from botasaurus.browser import Driver

from raxy.domain.accounts import Conta
from raxy.core.exceptions import (
    SessionException,
    ProxyRotationRequiredException,
    ProfileException,
    LoginException,
    InvalidCredentialsException,
    ElementNotFoundException,
    wrap_exception,
)
from raxy.interfaces.services import IProxyService, IMailTmService, ILoggingService
from raxy.services.base_service import BaseService

# Importações dos módulos desacoplados
from raxy.core.session import (
    SessionConfig,
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
    ) -> None:
        """
        Inicializa o serviço de sessão.
        
        Args:
            conta: Conta a ser utilizada
            proxy: Configuração de proxy
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
        self.proxy = proxy or {}
        
        # Estado da sessão
        self.driver: Driver | None = None
        self.cookies: dict[str, str] = {}
        self.user_agent: str = ""
        self.token_antifalsificacao: str | None = None
        
        # Serviços externos
        self._proxy_service = proxy_service
        self._mail_service = mail_service
        
        # Componentes internos
        self._profile_manager = ProfileManager(
            conta=conta,
            mail_service=mail_service,
            logger=self.logger
        )
        self._request_executor = RequestExecutor(
            logger=self.logger,
            proxy=self.proxy
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

        tentativas = SessionConfig.MAX_LOGIN_ATTEMPTS
        
        while tentativas > 0:
            try:
                # 2. Executar login via BrowserLoginHandler
                resultado = BrowserLoginHandler.executar_login(
                    profile=perfil_nome,
                    proxy=self.proxy.get("url"),
                    data=dados,
                    browser_arguments=user_agent_args
                )
                
                # 3. Atualizar estado da sessão
                self._atualizar_estado_sessao(resultado)
                break
                
            except ProxyRotationRequiredException as e:
                self._tratar_rotacao_proxy(e, tentativas)
            except (LoginException, InvalidCredentialsException, ElementNotFoundException):
                # Exceções de login não devem ser retentadas
                raise
            except Exception as e:
                self.logger.erro(
                    f"Erro inesperado ao abrir driver: {e}",
                    erro=e,
                    tentativas_restantes=tentativas-1
                )
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
                f"Falha ao iniciar a sessão após {SessionConfig.MAX_LOGIN_ATTEMPTS} tentativas.",
                details={"conta": self.conta.email, "proxy_id": self.proxy.get("id")}
            )

        self.logger.sucesso("Sessão iniciada com sucesso.")
    
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
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.erro(f"Erro ao fechar driver: {e}")
            finally:
                self.driver = None
                self.cookies = {}
                self.user_agent = ""
                self.token_antifalsificacao = None
        
        self.logger.debug("Sessão fechada")
    
    def __repr__(self) -> str:
        """Representação string do serviço."""
        status = "ativa" if self.driver else "inativa"
        return f"SessionManagerService(conta={self.conta.email}, sessão={status})"