"""
Classe base para clientes de API.

Define funcionalidades comuns para todos os clientes de API.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, List

import requests
from requests import Response

from raxy.core.exceptions import (
    APIException,
    InvalidAPIResponseException,
    JSONParsingException,
    RateLimitException,
    RequestTimeoutException,
    wrap_exception,
)
from raxy.interfaces.services import ILoggingService


class BaseAPIClient(ABC):
    """
    Classe base abstrata para clientes de API.
    
    Fornece funcionalidades comuns como tratamento de erros,
    retry logic, rate limiting e logging.
    """
    
    # Diretório de templates
    TEMPLATES_DIR = Path(__file__).resolve().parent / "requests_templates"
    
    def __init__(
        self,
        base_url: str,
        logger: Optional[ILoggingService] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_backoff: float = 1.5,
        rate_limit_delay: float = 0.5,
        error_words: Optional[List[str]] = None,
    ):
        """
        Inicializa o cliente de API.
        
        Args:
            base_url: URL base da API
            logger: Serviço de logging
            timeout: Timeout para requisições (segundos)
            max_retries: Número máximo de tentativas
            retry_backoff: Multiplicador de backoff para retry
            rate_limit_delay: Delay entre requisições (segundos)
            error_words: Palavras que indicam erro na resposta
        """
        self.base_url = base_url.rstrip('/')
        self._logger = logger or self._get_default_logger()
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.rate_limit_delay = rate_limit_delay
        self.error_words = tuple(word.lower() for word in (error_words or ["error", "captcha", "unavailable"]))
        
        # Session para reutilização de conexões
        self._session = requests.Session()
        self._session.headers.update(self._get_default_headers())
    
    def _get_default_logger(self) -> ILoggingService:
        """Obtém logger padrão."""
        from raxy.core.logging import get_logger
        return get_logger()
    
    def _get_default_headers(self) -> Dict[str, str]:
        """
        Retorna headers padrão para requisições.
        
        Returns:
            Dict[str, str]: Headers padrão
        """
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
    
    def load_template(self, template_name: str) -> Dict[str, Any]:
        """
        Carrega um template JSON.
        
        Args:
            template_name: Nome do arquivo de template
            
        Returns:
            Dict[str, Any]: Template carregado
            
        Raises:
            APIException: Se erro ao carregar template
        """
        template_path = self.TEMPLATES_DIR / template_name
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError as e:
            raise wrap_exception(
                e, APIException,
                f"Template não encontrado: {template_name}",
                template_path=str(template_path)
            )
        except json.JSONDecodeError as e:
            raise wrap_exception(
                e, JSONParsingException,
                f"Template contém JSON inválido: {template_name}",
                template_path=str(template_path)
            )
        except Exception as e:
            raise wrap_exception(
                e, APIException,
                f"Erro ao carregar template: {template_name}",
                template_path=str(template_path)
            )
    
    def check_response_for_errors(self, response: Response, context: str = "") -> None:
        """
        Verifica a resposta por erros conhecidos.
        
        Args:
            response: Resposta HTTP
            context: Contexto da requisição
            
        Raises:
            InvalidAPIResponseException: Se erro detectado
        """
        # Verifica status HTTP
        if not response.ok:
            if response.status_code == 429:
                raise RateLimitException(
                    f"Rate limit atingido: {context}",
                    details={"status_code": response.status_code}
                )
            elif response.status_code >= 400:
                raise InvalidAPIResponseException(
                    f"Erro HTTP {response.status_code}: {context}",
                    details={
                        "status_code": response.status_code,
                        "reason": response.reason,
                        "context": context
                    }
                )
        
        # Verifica palavras de erro no conteúdo
        try:
            text_lower = response.text.lower()
            for error_word in self.error_words:
                if error_word in text_lower:
                    raise InvalidAPIResponseException(
                        f"Resposta contém termo de erro: {error_word}",
                        details={
                            "error_word": error_word,
                            "context": context,
                            "preview": response.text[:200]
                        }
                    )
        except Exception as e:
            if isinstance(e, InvalidAPIResponseException):
                raise
            # Ignora outros erros ao verificar texto
    
    def parse_json_response(self, response: Response, context: str = "") -> Dict[str, Any]:
        """
        Parse de resposta JSON com tratamento de erros.
        
        Args:
            response: Resposta HTTP
            context: Contexto da requisição
            
        Returns:
            Dict[str, Any]: JSON parseado
            
        Raises:
            JSONParsingException: Se erro no parse
        """
        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise wrap_exception(
                e, JSONParsingException,
                f"Erro ao decodificar JSON: {context}",
                status_code=response.status_code,
                preview=response.text[:200]
            )
    
    def make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Response:
        """
        Faz uma requisição HTTP com retry e tratamento de erros.
        
        Args:
            method: Método HTTP
            endpoint: Endpoint da API
            **kwargs: Argumentos adicionais para requests
            
        Returns:
            Response: Resposta da requisição
            
        Raises:
            APIException: Se erro na requisição
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Define timeout padrão
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        
        # Log da requisição
        self._logger.debug(
            f"API Request: {method} {url}",
            method=method,
            url=url,
            params=kwargs.get('params'),
            has_data='data' in kwargs or 'json' in kwargs
        )
        
        # Tenta com retry
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._session.request(method, url, **kwargs)
                
                # Log da resposta
                self._logger.debug(
                    f"API Response: {response.status_code}",
                    status_code=response.status_code,
                    url=url
                )
                
                return response
                
            except requests.Timeout as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_backoff ** attempt
                    self._logger.aviso(
                        f"Timeout na tentativa {attempt + 1}, aguardando {wait_time}s",
                        url=url
                    )
                    import time
                    time.sleep(wait_time)
                    
            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    self._logger.aviso(
                        f"Erro na tentativa {attempt + 1}: {e}",
                        url=url
                    )
        
        # Se chegou aqui, todas as tentativas falharam
        if isinstance(last_error, requests.Timeout):
            raise wrap_exception(
                last_error, RequestTimeoutException,
                f"Timeout após {self.max_retries} tentativas",
                url=url
            )
        else:
            raise wrap_exception(
                last_error, APIException,
                f"Requisição falhou após {self.max_retries} tentativas",
                url=url
            )
    
    def close(self) -> None:
        """Fecha a sessão HTTP."""
        self._session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    @property
    def logger(self) -> ILoggingService:
        """Acesso ao logger."""
        return self._logger
