"""
Classe base para clientes de API.
"""

from __future__ import annotations

import json
from abc import ABC
from pathlib import Path
from typing import Any, Dict, Optional, List


class BaseAPIClient(ABC):
    """
    Classe base para clientes de API.
    
    Fornece funcionalidades comuns:
    - Carregamento de templates JSON
    - Logger
    - Configurações básicas (base_url, timeout, error_words)
    
    As requisições HTTP devem usar SessionManagerService.execute_template()
    que já gerencia cookies, UA, proxy e retry.
    """
    
    TEMPLATES_DIR = Path(__file__).resolve().parent / "requests_templates"
    
    def __init__(
        self,
        base_url: str,
        logger: Optional[Any] = None,
        timeout: int = 30,
        error_words: Optional[List[str]] = None,
    ):
        """
        Inicializa o cliente de API.
        
        Args:
            base_url: URL base da API
            logger: Logger (opcional)
            timeout: Timeout em segundos
            error_words: Palavras que indicam erro na resposta
        """
        self.base_url = base_url.rstrip('/')
        self._logger = logger or self._get_logger()
        self.timeout = timeout
        self.error_words = tuple(word.lower() for word in (error_words or []))
    
    def _get_logger(self) -> Any:
        """Obtém logger padrão."""
        from raxy.core.logging import get_logger
        return get_logger()
    
    def load_template(self, template_name: str) -> Dict[str, Any]:
        """Carrega template JSON."""
        with open(self.TEMPLATES_DIR / template_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @property
    def logger(self) -> Any:
        """Logger."""
        return self._logger

    def validate_response(self, response: Any, context_info: Optional[Dict[str, Any]] = None) -> None:
        """
        Valida a resposta da API.
        
        Args:
            response: Objeto de resposta (requests.Response ou compatível)
            context_info: Informações de contexto para erro
            
        Raises:
            InvalidAPIResponseException: Se resposta inválida
            Exception: Se conter palavras de erro configuradas
        """
        from raxy.core.exceptions import InvalidAPIResponseException
        
        # Verifica se resposta é None
        if response is None:
            raise InvalidAPIResponseException("Resposta nula da API")

        # Verifica status ok se disponível
        if hasattr(response, "ok") and not response.ok:
            raise InvalidAPIResponseException(
                f"Request falhou com status {getattr(response, 'status_code', 'N/A')}",
                details={
                    "status_code": getattr(response, "status_code", None),
                    **(context_info or {})
                }
            )

        # Verifica se há corpo na resposta
        text = getattr(response, "text", "")
        if not text and getattr(response, "status_code", 0) != 204:
            raise InvalidAPIResponseException(
                "Resposta sem corpo",
                details={
                    "status_code": getattr(response, "status_code", None),
                    **(context_info or {})
                }
            )
        
        # Verifica palavras de erro
        if self.error_words:
            text_lower = text.lower()
            for error_word in self.error_words:
                if error_word in text_lower:
                    # Aqui lançamos uma exceção genérica que pode ser capturada e re-lançada
                    # com tipo específico pela classe filha
                    raise Exception(f"Resposta contém termo de erro: {error_word}")

    def safe_json_parse(self, response: Any) -> Any:
        """
        Faz parse seguro de JSON.
        
        Args:
            response: Objeto de resposta
            
        Returns:
            Any: Dados parseados
            
        Raises:
            JSONParsingException: Se erro no parse
        """
        from raxy.core.exceptions import JSONParsingException, wrap_exception
        
        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise wrap_exception(
                e, JSONParsingException,
                "Erro ao decodificar resposta JSON",
                status_code=getattr(response, "status_code", None)
            )

    def load_and_copy_template(self, template_name: str) -> Dict[str, Any]:
        """
        Carrega e retorna uma cópia profunda do template.
        
        Args:
            template_name: Nome do arquivo de template
            
        Returns:
            Dict[str, Any]: Cópia do template
        """
        from copy import deepcopy
        template = self.load_template(template_name)
        return deepcopy(template)

    def _request(self, method: str, endpoint: str, session: Optional[Any] = None, **kwargs) -> Any:
        """
        Executa requisição HTTP segura.
        
        Args:
            method: Método HTTP
            endpoint: Endpoint (será concatenado com base_url)
            session: Sessão requests (opcional, usa self.session se existir ou cria nova)
            **kwargs: Argumentos para requests.request
            
        Returns:
            Any: JSON da resposta ou None
            
        Raises:
            RequestException: Erro de conexão/requisição
            RequestTimeoutException: Timeout
            Exception: Erro genérico da API
        """
        import requests
        from raxy.core.exceptions import RequestException, RequestTimeoutException, wrap_exception
        
        url = f"{self.base_url}{endpoint}"
        
        # Usa sessão fornecida, ou self.session se existir, ou requests direto
        sess = session
        if sess is None and hasattr(self, "session"):
            sess = self.session
        
        try:
            if sess:
                response = sess.request(method, url, **kwargs)
            else:
                response = requests.request(method, url, **kwargs)
                
            response.raise_for_status()
            
            if response.status_code == 204:
                return None
                
            return response.json()
            
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout ao acessar {url}"
            self.logger.erro(error_msg)
            raise RequestTimeoutException(
                error_msg,
                details={"url": url, "method": method, "endpoint": endpoint}
            ) from e
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            error_msg = f"Erro na API: {status_code} - {e.response.text if e.response else 'Sem resposta'}"
            self.logger.erro(f"Erro HTTP ao acessar {url}: {error_msg}")
            # Aqui lançamos Exception genérica, subclasses devem capturar e lançar específica
            raise Exception(error_msg) from e
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Erro de conexão ao acessar {url}"
            self.logger.erro(error_msg)
            raise RequestException(
                error_msg,
                details={"url": url, "method": method}
            ) from e
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Erro de requisição: {e}"
            self.logger.erro(f"Erro ao acessar {url}: {e}")
            raise wrap_exception(
                e, RequestException,
                error_msg,
                url=url, method=method
            )

    def safe_execute(self, func: Any, error_class: Any, error_msg: str, **context) -> Any:
        """
        Executa função protegida por try/except.
        
        Args:
            func: Função a executar
            error_class: Classe de exceção a lançar em caso de erro
            error_msg: Mensagem de erro
            **context: Contexto para detalhes do erro
            
        Returns:
            Any: Resultado da função
        """
        from raxy.core.exceptions import wrap_exception
        
        try:
            return func()
        except error_class:
            raise
        except Exception as e:
            raise wrap_exception(
                e, error_class,
                error_msg,
                **context
            )
