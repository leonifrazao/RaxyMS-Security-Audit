"""
API refatorada para sugestões de pesquisa do Bing.

Fornece interface para obter sugestões de busca do Bing de forma
modular e com tratamento robusto de erros.
"""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from raxy.interfaces.services import IBingSuggestion, ILoggingService
from raxy.core.session_manager_service import SessionManagerService
from raxy.core.exceptions import (
    BingAPIException,
    InvalidAPIResponseException,
    InvalidInputException,
    wrap_exception,
)
from .base_api import BaseAPIClient


class BingSuggestionConfig:
    """Configuração para API de sugestões do Bing."""
    
    # URLs e endpoints
    BASE_URL = "https://www.bing.com"
    SUGGESTION_ENDPOINT = "/AS/Suggestions"
    
    # Templates
    TEMPLATE_FILE = "suggestion_search.json"
    
    # Palavras de erro
    DEFAULT_ERROR_WORDS = ["captcha", "temporarily unavailable", "error", "blocked"]
    
    # Parâmetros de query
    QUERY_PARAM = "qry"


class SuggestionParser:
    """Parser para respostas de sugestões."""
    
    @staticmethod
    def parse_suggestions(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extrai sugestões da resposta.
        
        Args:
            response_data: Dados da resposta
            
        Returns:
            List[Dict[str, Any]]: Lista de sugestões
            
        Raises:
            InvalidAPIResponseException: Se formato inválido
        """
        suggestions = response_data.get("s")
        
        if not isinstance(suggestions, list):
            raise InvalidAPIResponseException(
                "Resposta não contém lista de sugestões válida",
                details={
                    "response_type": type(suggestions).__name__,
                    "response_keys": list(response_data.keys()) if isinstance(response_data, dict) else None
                }
            )
        
        return suggestions
    
    @staticmethod
    def update_url_with_query(url: str, query: str) -> str:
        """
        Atualiza URL com a query de busca.
        
        Args:
            url: URL original
            query: Query de busca
            
        Returns:
            str: URL atualizada
        """
        try:
            parsed = urlparse(url)
            params = list(parse_qsl(parsed.query, keep_blank_values=True))
            
            # Atualiza ou adiciona parâmetro de query
            query_updated = False
            for i, (key, _) in enumerate(params):
                if key == BingSuggestionConfig.QUERY_PARAM:
                    params[i] = (key, query)
                    query_updated = True
                    break
            
            if not query_updated:
                params.append((BingSuggestionConfig.QUERY_PARAM, query))
            
            new_query = urlencode(params, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
            
        except Exception:
            # Se falhar, retorna URL original
            return url


class BingSuggestionAPI(BaseAPIClient, IBingSuggestion):
    """
    Cliente de API para sugestões do Bing.
    
    Implementa a interface IBingSuggestion com arquitetura modular
    e tratamento robusto de erros.
    """
    
    def __init__(
        self,
        logger: Optional[ILoggingService] = None,
        palavras_erro: Optional[Sequence[str]] = None
    ):
        """
        Inicializa o cliente de sugestões.
        
        Args:
            logger: Serviço de logging
            palavras_erro: Palavras que indicam erro na resposta
        """
        super().__init__(
            base_url=BingSuggestionConfig.BASE_URL,
            logger=logger,
            error_words=palavras_erro or BingSuggestionConfig.DEFAULT_ERROR_WORDS
        )
        
        self.config = BingSuggestionConfig()
        self.parser = SuggestionParser()

    def get_all(self, sessao: SessionManagerService, keyword: str) -> List[Dict[str, Any]]:
        """
        Obtém todas as sugestões para uma palavra-chave.
        
        Args:
            sessao: Sessão do usuário
            keyword: Palavra-chave para buscar sugestões
            
        Returns:
            List[Dict[str, Any]]: Lista de sugestões
            
        Raises:
            InvalidInputException: Se entrada inválida
            BingAPIException: Se erro na API
        """
        # Valida entrada
        self._validate_keyword(keyword)
        
        self.logger.debug(f"Obtendo sugestões para: {keyword}")
        
        # Carrega e prepara template
        template = self._prepare_template(keyword.strip())
        
        # Executa requisição via sessão
        try:
            response = sessao.execute_template(
                template,
                bypass_request_token=False
            )
        except Exception as e:
            raise wrap_exception(
                e, BingAPIException,
                "Erro ao executar requisição de sugestões",
                keyword=keyword
            )
        
        # Valida resposta
        self._validate_response(response, keyword)
        
        # Parse da resposta
        try:
            response_data = response.json()
        except Exception as e:
            raise wrap_exception(
                e, BingAPIException,
                "Erro ao decodificar resposta JSON",
                keyword=keyword
            )
        
        # Extrai sugestões
        suggestions = self.parser.parse_suggestions(response_data)
        
        self.logger.info(
            f"Obtidas {len(suggestions)} sugestões",
            keyword=keyword,
            count=len(suggestions)
        )
        
        return suggestions

    def get_random(self, sessao: SessionManagerService, keyword: str) -> Dict[str, Any]:
        """
        Obtém uma sugestão aleatória.
        
        Args:
            sessao: Sessão do usuário
            keyword: Palavra-chave para buscar sugestões
            
        Returns:
            Dict[str, Any]: Sugestão aleatória
            
        Raises:
            BingAPIException: Se erro ou nenhuma sugestão encontrada
        """
        suggestions = self.get_all(sessao, keyword)
        
        if not suggestions:
            raise BingAPIException(
                f"Nenhuma sugestão encontrada para: {keyword}",
                details={"keyword": keyword}
            )
        
        selected = random.choice(suggestions)
        
        self.logger.debug(
            "Sugestão aleatória selecionada",
            keyword=keyword,
            suggestion=selected
        )
        
        return selected

    def _validate_keyword(self, keyword: str) -> None:
        """
        Valida a palavra-chave.
        
        Args:
            keyword: Palavra-chave
            
        Raises:
            InvalidInputException: Se inválida
        """
        if not isinstance(keyword, str) or not keyword.strip():
            raise InvalidInputException(
                "Palavra-chave não pode ser vazia",
                details={
                    "keyword": keyword,
                    "type": type(keyword).__name__
                }
            )
    
    def _prepare_template(self, keyword: str) -> Dict[str, Any]:
        """
        Prepara template com a palavra-chave.
        
        Args:
            keyword: Palavra-chave
            
        Returns:
            Dict[str, Any]: Template preparado
        """
        # Carrega template base
        template = self.load_template(self.config.TEMPLATE_FILE)
        
        # Faz cópia profunda para não modificar original
        template_copy = deepcopy(template)
        
        # Atualiza URL com query
        if "url" in template_copy and isinstance(template_copy["url"], str):
            template_copy["url"] = self.parser.update_url_with_query(
                template_copy["url"],
                keyword
            )
        
        return template_copy
    
    def _validate_response(self, response: Any, keyword: str) -> None:
        """
        Valida a resposta da API.
        
        Args:
            response: Resposta da API
            keyword: Palavra-chave usada
            
        Raises:
            InvalidAPIResponseException: Se resposta inválida
        """
        # Verifica se há corpo na resposta
        text = getattr(response, "text", "")
        if not text:
            raise InvalidAPIResponseException(
                "Resposta sem corpo",
                details={
                    "status_code": getattr(response, "status_code", None),
                    "keyword": keyword
                }
            )
        
        # Verifica palavras de erro
        text_lower = text.lower()
        for error_word in self.error_words:
            if error_word in text_lower:
                raise BingAPIException(
                    f"Resposta contém termo de erro: {error_word}",
                    details={
                        "keyword": keyword,
                        "error_word": error_word,
                        "preview": text[:200]
                    }
                )
