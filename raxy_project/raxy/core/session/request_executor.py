"""
Executor de requisições para o SessionManagerService.

Responsável por executar templates de requisição com tratamento robusto.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Dict
import time
from botasaurus.request import Request, request

from raxy.core.session.session_utils import replace_placeholders
from raxy.core.exceptions import (
    SessionException,
    ProxyRotationRequiredException,
    wrap_exception
)
from raxy.core.logging import debug_log
from raxy.interfaces.services import ILoggingService
from raxy.services.base_service import BaseService


class RequestExecutor(BaseService):
    """
    Executor de templates de requisição.
    
    Responsável por:
    - Carregar templates de requisição
    - Substituir placeholders
    - Adicionar headers e cookies necessários
    - Executar requisições via Botasaurus request
    - Tratar erros e status HTTP
    """
    
    def __init__(
        self,
        cookies: dict[str, str] | None = None,
        user_agent: str | None = None,
        token_antifalsificacao: str | None = None,
        proxy: dict | None = None,
        logger: Optional[ILoggingService] = None,
        event_bus: Optional[Any] = None
    ):
        """
        Inicializa o executor de requisições.
        
        Args:
            cookies: Cookies da sessão
            user_agent: User-Agent da sessão
            token_antifalsificacao: Token de verificação
            proxy: Configuração de proxy
            logger: Serviço de logging (opcional)
            event_bus: Event Bus para publicação de eventos
        """
        super().__init__(logger)
        self.cookies = cookies or {}
        self.user_agent = user_agent or ""
        self.token_antifalsificacao = token_antifalsificacao
        self.proxy = proxy or {}
        self._event_bus = event_bus
    
    def _publish_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Publica evento no Event Bus se disponível."""
        if self._event_bus and hasattr(self._event_bus, 'publish'):
            try:
                self._event_bus.publish(event_name, data)
            except Exception:
                pass
    
    def atualizar_sessao(
        self,
        cookies: dict[str, str] | None = None,
        user_agent: str | None = None,
        token_antifalsificacao: str | None = None
    ):
        """
        Atualiza dados da sessão.
        
        Args:
            cookies: Novos cookies
            user_agent: Novo User-Agent
            token_antifalsificacao: Novo token
        """
        if cookies is not None:
            self.cookies = cookies
        if user_agent is not None:
            self.user_agent = user_agent
        if token_antifalsificacao is not None:
            self.token_antifalsificacao = token_antifalsificacao
    
    @debug_log(log_args=False, log_result=False, log_duration=True)
    def executar_template(
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
        
        Args:
            template_path_or_dict: Caminho para o template ou dicionário
            placeholders: Valores para substituir no template
            use_ua: Se deve usar o User-Agent da sessão
            use_cookies: Se deve usar os cookies da sessão
            bypass_request_token: Se deve adicionar token de verificação
            
        Returns:
            Resposta da requisição
            
        Raises:
            SessionException: Se houver erro ao carregar/executar template
            ProxyRotationRequiredException: Se status HTTP >= 400
        """
        # Carrega o template
        template = self._carregar_template(template_path_or_dict)
        
        # Substitui placeholders
        if placeholders:
            template = replace_placeholders(template, placeholders)
        
        # Prepara argumentos da requisição
        args = self._preparar_argumentos(
            template, 
            use_ua=use_ua,
            use_cookies=use_cookies,
            bypass_request_token=bypass_request_token
        )
        
        # Executa a requisição
        return self._executar_requisicao(args)
    
    def _carregar_template(
        self, 
        template_path_or_dict: str | Path | Mapping[str, Any]
    ) -> dict[str, Any]:
        """
        Carrega um template de arquivo ou dicionário.
        
        Args:
            template_path_or_dict: Caminho ou dicionário do template
            
        Returns:
            Template como dicionário
            
        Raises:
            SessionException: Se houver erro ao carregar
        """
        try:
            if isinstance(template_path_or_dict, (str, Path)):
                with open(template_path_or_dict, encoding="utf-8") as f:
                    return json.load(f)
            else:
                return dict(template_path_or_dict)
        except FileNotFoundError as e:
            raise wrap_exception(
                e, SessionException,
                "Template não encontrado",
                template=str(template_path_or_dict)
            )
        except json.JSONDecodeError as e:
            raise wrap_exception(
                e, SessionException,
                "Template JSON inválido",
                template=str(template_path_or_dict)
            )
        except Exception as e:
            raise wrap_exception(
                e, SessionException,
                "Erro ao carregar template",
                template=str(template_path_or_dict)
            )
    
    def _preparar_argumentos(
        self,
        template: dict[str, Any],
        use_ua: bool,
        use_cookies: bool,
        bypass_request_token: bool
    ) -> dict[str, Any]:
        """
        Prepara argumentos para a requisição.
        
        Args:
            template: Template carregado
            use_ua: Se deve usar User-Agent
            use_cookies: Se deve usar cookies
            bypass_request_token: Se deve adicionar token
            
        Returns:
            Argumentos preparados para a requisição
        """
        metodo = str(template.get("method", "GET")).lower()
        url = template.get("url") or template.get("path")
        headers = dict(template.get("headers") or {})
        cookies = dict(template.get("cookies") or {})
        
        # Adiciona User-Agent
        if use_ua and self.user_agent:
            headers.setdefault("User-Agent", self.user_agent)
        
        # Adiciona cookies
        if use_cookies:
            cookies = {**self.cookies, **cookies}
        
        # Prepara dados
        data = template.get("data")
        json_payload = template.get("json")
        
        # Adiciona token de verificação
        if bypass_request_token and self.token_antifalsificacao and metodo in {"post", "put", "patch", "delete"}:
            if isinstance(data, dict) and not data.get("__RequestVerificationToken"):
                data["__RequestVerificationToken"] = self.token_antifalsificacao
            if isinstance(json_payload, dict) and not json_payload.get("__RequestVerificationToken"):
                json_payload["__RequestVerificationToken"] = self.token_antifalsificacao
            headers.setdefault("RequestVerificationToken", self.token_antifalsificacao)
        
        return {
            "metodo": metodo,
            "url": url,
            "headers": headers,
            "cookies": cookies,
            "data": data,
            "json": json_payload,
        }
    
    def _executar_requisicao(self, args: dict[str, Any]) -> Any:
        """
        Executa a requisição via Botasaurus.
        
        Args:
            args: Argumentos da requisição
            
        Returns:
            Resposta da requisição
            
        Raises:
            SessionException: Se houver erro ao enviar
            ProxyRotationRequiredException: Se status HTTP >= 400
        """
        try:
            resposta = self._enviar(args, proxy=self.proxy.get("url"))
        except Exception as e:
            raise wrap_exception(
                e, SessionException,
                "Erro ao enviar requisição",
                url=args.get("url"), 
                metodo=args.get("metodo")
            )
        
        # Verifica status HTTP
        status = getattr(resposta, "status_code", None)
        
        if status:
            self._publish_event("request.completed", {
                "url": args.get("url"),
                "method": args.get("metodo"),
                "status_code": status,
                "success": status < 400,
                "timestamp": time.time(),
            })
        
        if status and status >= 400:
            raise ProxyRotationRequiredException(
                status, 
                self.proxy.get("id"), 
                url=args.get("url")
            )
        
        return resposta
    
    @staticmethod
    @request(cache=False, raise_exception=True, create_error_logs=False, output=None)
    def _enviar(req: Request, args: dict, proxy: str | None = None):
        """
        Método estático decorado para enviar requisições.
        
        Args:
            req: Objeto Request do Botasaurus
            args: Argumentos da requisição
            proxy: URL do proxy
            
        Returns:
            Resposta da requisição
        """
        metodo = args.pop("metodo")
        return getattr(req, metodo)(**args)
