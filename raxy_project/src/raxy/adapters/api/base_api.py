"""
Base API Client com suporte integrado a Botasaurus.

Fornece método `executar()` para requisições HTTP com suporte a:
- Proxy
- Sessão (cookies + user_agent)
- Templates de requisição
- Integração com SessionManagerService
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, List

from botasaurus.request import Request, request as botasaurus_request

# Templates directory
TEMPLATES_DIR = Path(__file__).resolve().parent / "requests_templates"


class BaseAPIClient:
    """
    Base class for API clients with built-in Botasaurus HTTP support.
    
    Uso simples:
        api = MyAPI(session=session_manager)
        response = api.executar("GET", "/endpoint")
    
    Ou sem sessão:
        api = MyAPI()
        api.set_proxy("http://proxy:8080")
        response = api.executar("POST", "/endpoint", json={"data": "value"})
    """
    
    def __init__(
        self,
        base_url: str = "",
        logger: Optional[Any] = None,
        timeout: int = 30,
        error_words: Optional[List[str]] = None,
        proxy: Optional[str] = None,
        cookies: Optional[Dict[str, str]] = None,
        session: Optional[Any] = None,
    ):
        self.base_url = base_url.rstrip('/') if base_url else ""
        self._logger = logger or self._get_default_logger()
        self.timeout = timeout
        self.error_words = tuple(word.lower() for word in (error_words or []))
        
        # Sessão (SessionManagerService)
        self._session = session
        self._user_agent: Optional[str] = None
        
        # Inicializa com sessão ou valores diretos
        if session is not None:
            self._init_from_session(session)
        else:
            self.proxy = proxy
            self.cookies = cookies or {}
    
    def _init_from_session(self, session: Any) -> None:
        """Inicializa proxy, cookies e UA a partir de uma sessão."""
        # Proxy
        proxy = getattr(session, 'proxy', None)
        if proxy and hasattr(proxy, 'url') and getattr(proxy, 'is_valid', False):
            self.proxy = proxy.url
        else:
            self.proxy = None
        
        # Cookies e User-Agent
        self.cookies = getattr(session, 'cookies', {}) or {}
        self._user_agent = getattr(session, 'user_agent', None)
    
    @classmethod
    def from_session(cls, session: Any, base_url: str = "", **kwargs) -> "BaseAPIClient":
        """Cria um cliente a partir de uma SessionManagerService."""
        return cls(base_url=base_url, session=session, **kwargs)
    
    def set_session(self, session: Any) -> None:
        """Configura o cliente a partir de uma SessionManagerService."""
        self._session = session
        self._init_from_session(session)
    
    def _get_default_logger(self) -> Any:
        from raxy.infrastructure.logging import get_logger 
        return get_logger()
    
    @property
    def logger(self) -> Any:
        return self._logger
    
    def set_proxy(self, proxy: str) -> None:
        """Define o proxy para requisições."""
        self.proxy = proxy
    
    def set_cookies(self, cookies: Dict[str, str]) -> None:
        """Define cookies da sessão."""
        self.cookies = cookies
    
    def update_cookies(self, cookies: Dict[str, str]) -> None:
        """Atualiza cookies da sessão (merge)."""
        self.cookies.update(cookies)

    # ==================== Main Request Method ====================
    
    def executar(
        self,
        method: str,
        endpoint: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        cookies: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Executa uma requisição HTTP.
        
        Args:
            method: Método HTTP (GET, POST, PUT, PATCH, DELETE)
            endpoint: Endpoint ou URL completa
            headers: Headers adicionais
            params: Query parameters
            data: Dados do corpo (form)
            json: Dados do corpo (JSON)
            cookies: Cookies adicionais
            
        Returns:
            Resposta parseada (JSON se disponível)
        """
        # Monta URL
        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = f"{self.base_url}{endpoint}"
        
        # Prepara headers com User-Agent da sessão
        final_headers = headers.copy() if headers else {}
        if self._user_agent and "User-Agent" not in final_headers:
            final_headers["User-Agent"] = self._user_agent
        
        # Merge cookies
        final_cookies = {**self.cookies, **(cookies or {})}
        
        # Prepara dados para o request
        request_data = {
            "method": method.lower(),
            "url": url,
            "headers": final_headers,
            "params": params,
            "data": data,
            "json_data": json,
            "cookies": final_cookies,
        }
        
        try:
            response = _make_request(request_data, proxy=self.proxy)
            
            # Atualiza cookies da resposta
            if hasattr(response, 'cookies'):
                for key, value in response.cookies.items():
                    self.cookies[key] = value
            
            # Valida
            self._validate_response(response, url=url)
            
            # Retorna JSON se possível
            if hasattr(response, "status_code") and response.status_code == 204:
                return None
            
            if hasattr(response, 'json'):
                return response.json()
            
            return response
            
        except Exception as e:
            self.logger.erro(f"Error accessing {url}: {e}")
            raise

    def _validate_response(self, response: Any, url: str = "") -> None:
        """Valida a resposta HTTP."""
        if response is None:
            raise Exception("Null API response")

        if hasattr(response, "status_code") and response.status_code >= 400:
            raise Exception(f"Request failed with status {response.status_code}")

        text = getattr(response, "text", "")
        if not text and getattr(response, "status_code", 0) != 204:
            raise Exception("Empty response body")
        
        if self.error_words:
            text_lower = text.lower()
            for error_word in self.error_words:
                if error_word in text_lower:
                    raise Exception(f"Response contains error word: {error_word}")

    # ==================== Templates ====================
    
    def load_template(self, template_name: str) -> Dict[str, Any]:
        """Loads a JSON template."""
        template_path = TEMPLATES_DIR / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_and_copy_template(self, template_name: str) -> Dict[str, Any]:
        """Loads and returns a deep copy of a template."""
        return deepcopy(self.load_template(template_name))

    def execute_template(self, template: Dict[str, Any]) -> Any:
        """Executa uma requisição a partir de um template."""
        method = template.get("method", "GET")
        url = template.get("url", "")
        headers = template.get("headers", {})
        
        return self.executar(method, url, headers=headers)

    # ==================== Helpers ====================
    
    def safe_execute(
        self,
        callable_fn: Any,
        exception_class: type = Exception,
        error_message: str = "Erro na operação",
        **context: Any
    ) -> Any:
        """Executa uma função de forma segura."""
        try:
            return callable_fn()
        except exception_class as e:
            self.logger.erro(f"{error_message}: {e}", **context)
            raise
        except Exception as e:
            self.logger.erro(f"{error_message}: {e}", **context)
            return None

    def safe_json_parse(self, response: Any) -> Dict[str, Any]:
        """Parse JSON de resposta de forma segura."""
        if isinstance(response, dict):
            return response
        if hasattr(response, 'json'):
            return response.json()
        if isinstance(response, str):
            return json.loads(response)
        return {}


# ==================== Botasaurus Request Function ====================

@botasaurus_request(cache=False, raise_exception=True, create_error_logs=False, output=None, max_retry=3, retry_wait=2)
def _make_request(req: Request, data: dict, proxy: str | None = None):
    """Função decorada com Botasaurus para fazer requisições HTTP."""
    method = data["method"]
    url = data["url"]
    
    kwargs = {}
    if data.get("headers"):
        kwargs["headers"] = data["headers"]
    if data.get("params"):
        kwargs["params"] = data["params"]
    if data.get("data"):
        kwargs["data"] = data["data"]
    if data.get("json_data"):
        kwargs["json"] = data["json_data"]
    if data.get("cookies"):
        kwargs["cookies"] = data["cookies"]
    
    request_method = getattr(req, method)
    return request_method(url, **kwargs)
