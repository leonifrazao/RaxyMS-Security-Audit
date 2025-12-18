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

from raxy.core.exceptions import (
    BingAPIException,
    InvalidAPIResponseException,
    InvalidInputException,
    wrap_exception,
)
from raxy.core.config import get_config
from raxy.core.logging import debug_log
from .base_api import BaseAPIClient


# Constantes locais (não configuráveis)
BASE_URL = "https://www.bing.com"
SUGGESTION_ENDPOINT = "/AS/Suggestions"
TEMPLATE_FILE = "suggestion_search.json"
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
                if key == QUERY_PARAM:
                    params[i] = (key, query)
                    query_updated = True
                    break
            
            if not query_updated:
                params.append((QUERY_PARAM, query))
            
            new_query = urlencode(params, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
            
        except Exception:
            # Se falhar, retorna URL original
            return url


class BingSuggestionAPI(BaseAPIClient):
    """
    Cliente de API para sugestões do Bing.
    
    Implementa a interface IBingSuggestion com arquitetura modular
    e tratamento robusto de erros.
    """
    
    def __init__(
        self,
        logger: Optional[Any] = None,
        palavras_erro: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(
            base_url=BASE_URL,
            logger=logger,
            error_words=palavras_erro or get_config().api.bing_suggestion_error_words
        )
        
        self.parser = SuggestionParser()

    @debug_log(log_args=True, log_result=False, log_duration=True)
    def get_all(
        self,
        sessao: Any,
        query: str,
        *,
        country: Optional[str] = None,
    ) -> Sequence[str]:
        """
        Obtém todas as sugestões para uma palavra-chave.
        
        Args:
            sessao: Sessão do usuário
            query: Palavra-chave para buscar sugestões
            
        Returns:
            Sequence[str]: Lista de sugestões
            
        Raises:
            InvalidInputException: Se entrada inválida
            BingAPIException: Se erro na API
        """
        
        # Valida entrada
        self._validate_keyword(query)
        
        self.logger.debug(f"Obtendo sugestões para: {query}")
        
        # Carrega e prepara template
        template = self._prepare_template(query.strip())
        
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
                keyword=query
            )
        
        # Valida resposta
        try:
            self.validate_response(response, context_info={"keyword": query})
        except Exception as e:
            if "termo de erro" in str(e):
                 raise BingAPIException(str(e), details={"keyword": query})
            raise

        # Parse da resposta
        response_data = self.safe_json_parse(response)
        
        # Extrai sugestões
        suggestions = self.parser.parse_suggestions(response_data)
        
        self.logger.info(
            f"Obtidas {len(suggestions)} sugestões",
            keyword=query,
            count=len(suggestions)
        )
        
        return suggestions

    @debug_log(log_args=True, log_result=True, log_duration=True)
    def get_random(
        self,
        sessao: Any,
        query: str,
        *,
        country: Optional[str] = None,
    ) -> Optional[str]:
        """
        Obtém uma sugestão aleatória.
        
        Args:
            sessao: Sessão do usuário
            query: Palavra-chave para buscar sugestões
            
        Returns:
            Optional[str]: Sugestão aleatória
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
        # Carrega template base (cópia profunda)
        template_copy = self.load_and_copy_template(TEMPLATE_FILE)
        
        # Atualiza URL com query
        if "url" in template_copy and isinstance(template_copy["url"], str):
            template_copy["url"] = self.parser.update_url_with_query(
                template_copy["url"],
                keyword
            )
        
        return template_copy
    

