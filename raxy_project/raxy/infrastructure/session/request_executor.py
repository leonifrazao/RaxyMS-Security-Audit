"""
Executor de requisições para o SessionManager.

Responsável por executar templates de requisição com tratamento robusto.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Dict
import time
from botasaurus.request import Request, request

from raxy.infrastructure.session.session_utils import replace_placeholders
from raxy.core.exceptions import (
    SessionException,
    ProxyRotationRequiredException,
    wrap_exception
)
from raxy.core.logging import debug_log
from raxy.interfaces.services import ILoggingService
from raxy.services.base_service import BaseService
from raxy.models.proxy import ProxyItem


class RequestExecutor(BaseService):
    """
    Executor de templates de requisição.
    
    Responsável por:
    - Carregar templates de requisição
    - Substituir placeholders
    - Adicionar headers e cookies necessários
    - Executar requisições via Botasaurus request
    - Tratar erros e status HTTP
    
    Stateless: Recebe todo o contexto da sessão (cookies, UA, etc) em cada execução.
    """
    
    def __init__(
        self,
        logger: Optional[ILoggingService] = None,
    ):
        """
        Inicializa o executor de requisições.
        
        Args:
            logger: Serviço de logging (opcional)
        """
        super().__init__(logger)
    
    @debug_log(log_args=False, log_result=False, log_duration=True)
    def executar_template(
        self,
        template_path_or_dict: str | Path | Mapping[str, Any],
        *,
        cookies: dict[str, str],
        user_agent: str,
        token_antifalsificacao: str | None = None,
        proxy: ProxyItem | None = None,
        placeholders: Mapping[str, Any] | None = None,
        use_ua: bool = True,
        use_cookies: bool = True,
        bypass_request_token: bool = True,
    ) -> Any:
        """
        Executa um template de requisição.
        
        Args:
            template_path_or_dict: Caminho para o template ou dicionário
            cookies: Cookies da sessão
            user_agent: User-Agent a ser usado
            token_antifalsificacao: Token de verificação anti-falsificação
            proxy: Proxy a ser usado
            placeholders: Valores para substituir no template
            use_ua: Se deve usar o User-Agent fornecido
            use_cookies: Se deve usar os cookies fornecidos
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
            cookies=cookies,
            user_agent=user_agent,
            token_antifalsificacao=token_antifalsificacao,
            use_ua=use_ua,
            use_cookies=use_cookies,
            bypass_request_token=bypass_request_token
        )
        
        # Executa a requisição
        return self._executar_requisicao(args, proxy=proxy)
    
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
        cookies: dict[str, str],
        user_agent: str,
        token_antifalsificacao: str | None,
        use_ua: bool,
        use_cookies: bool,
        bypass_request_token: bool
    ) -> dict[str, Any]:
        """
        Prepara argumentos para a requisição.
        
        Args:
            template: Template carregado
            cookies: Cookies da sessão
            user_agent: UA da sessão
            token_antifalsificacao: Token da sessão
            use_ua: Se deve usar User-Agent
            use_cookies: Se deve usar cookies
            bypass_request_token: Se deve adicionar token
            
        Returns:
            Argumentos preparados para a requisição
        """
        metodo = str(template.get("method", "GET")).lower()
        url = template.get("url") or template.get("path")
        headers = dict(template.get("headers") or {})
        cookies_req = dict(template.get("cookies") or {})
        
        # Adiciona User-Agent
        if use_ua and user_agent:
            headers.setdefault("User-Agent", user_agent)
        
        # Adiciona cookies
        if use_cookies:
            cookies_req = {**cookies, **cookies_req}
        
        # Prepara dados
        data = template.get("data")
        json_payload = template.get("json")
        
        # Adiciona token de verificação
        if bypass_request_token and token_antifalsificacao and metodo in {"post", "put", "patch", "delete"}:
            if isinstance(data, dict) and not data.get("__RequestVerificationToken"):
                data["__RequestVerificationToken"] = token_antifalsificacao
            if isinstance(json_payload, dict) and not json_payload.get("__RequestVerificationToken"):
                json_payload["__RequestVerificationToken"] = token_antifalsificacao
            headers.setdefault("RequestVerificationToken", token_antifalsificacao)
        
        return {
            "metodo": metodo,
            "url": url,
            "headers": headers,
            "cookies": cookies_req,
            "data": data,
            "json": json_payload,
        }
    
    def _executar_requisicao(self, args: dict[str, Any], proxy: ProxyItem | None = None) -> Any:
        """
        Executa a requisição via Botasaurus.
        
        Args:
            args: Argumentos da requisição
            proxy: Item de proxy a ser usado (opcional)
            
        Returns:
            Resposta da requisição
            
        Raises:
            SessionException: Se houver erro ao enviar
            ProxyRotationRequiredException: Se status HTTP >= 400
        """
        try:
            proxy_uri = proxy.uri if proxy else None
            resposta = self._enviar(args, proxy=proxy_uri)
        except Exception as e:
            raise wrap_exception(
                e, SessionException,
                "Erro ao enviar requisição",
                url=args.get("url"), 
                metodo=args.get("metodo")
            )
        
        # Verifica status HTTP
        status = getattr(resposta, "status_code", None)
        
        if status and status >= 400:
            raise ProxyRotationRequiredException(
                status, 
                proxy.tag if proxy else "unknown", 
                url=args.get("url")
            )
        
        return resposta
    
    @staticmethod
    @request(cache=False, raise_exception=True, create_error_logs=False, output=None, max_retry=5, retry_wait=2)
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
        kwargs = args.copy()
        metodo = kwargs.pop("metodo")
        return getattr(req, metodo)(**kwargs)

