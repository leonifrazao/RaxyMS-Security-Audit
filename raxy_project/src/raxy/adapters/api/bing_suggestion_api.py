"""
API refatorada para sugestões de pesquisa do Bing.

Fornece interface para obter sugestões de busca do Bing de forma
modular e com tratamento robusto de erros.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from raxy.core.exceptions import (
    BingAPIException,
    InvalidAPIResponseException,
    InvalidInputException,
)
from raxy.infrastructure.config.config import get_config
from raxy.infrastructure.logging import debug_log
from .base_api import BaseAPIClient


# Constantes locais (não configuráveis)
TEMPLATE_FILE = "suggestion_search.json"
QUERY_PARAM = "qry"


class SuggestionParser:
    """Parser para respostas de sugestões."""
    
    @staticmethod
    def parse_suggestions(response_data: Dict[str, Any]) -> List[str]:
        """
        Extrai sugestões da resposta do Bing.
        
        Args:
            response_data: Dados da resposta
            
        Returns:
            List[str]: Lista de strings de sugestão
        """
        suggestions = response_data.get("s", [])
        
        if not isinstance(suggestions, list):
            return []
        
        result = []
        for item in suggestions:
            if isinstance(item, dict) and 'q' in item:
                # Remove caracteres de marcação unicode (e000, e001)
                text = item['q'].replace('\ue000', '').replace('\ue001', '')
                result.append(text.strip())
            elif isinstance(item, str):
                result.append(item)
        
        return result
    
    @staticmethod
    def update_url_with_query(url: str, query: str) -> str:
        """Atualiza URL com a query de busca."""
        try:
            parsed = urlparse(url)
            params = list(parse_qsl(parsed.query, keep_blank_values=True))
            
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
            return url


class BingSuggestionAPI(BaseAPIClient):
    """
    Cliente de API para sugestões do Bing (anônimo).
    
    Funciona sem sessão de usuário, fazendo requisições diretas.
    """
    
    def __init__(
        self,
        logger: Optional[Any] = None,
        palavras_erro: Optional[Sequence[str]] = None,
    ) -> None:
        config = get_config()
        base_url = config.session.bing_url if hasattr(config, 'session') else "https://www.bing.com"
        
        super().__init__(
            base_url=base_url,
            logger=logger,
            error_words=palavras_erro or config.api.bing_suggestion.error_words
        )
        
        self.parser = SuggestionParser()

    @debug_log(log_args=True, log_result=False, log_duration=True)
    def get_all(self, query: str) -> List[str]:
        """
        Obtém todas as sugestões para uma palavra-chave.
        
        Args:
            query: Palavra-chave para buscar sugestões
            
        Returns:
            List[str]: Lista de sugestões
        """
        self._validate_keyword(query)
        
        self.logger.debug(f"Obtendo sugestões para: {query}")
        
        # Carrega e prepara template
        template = self._prepare_template(query.strip())
        
        try:
            response = self.execute_template(template)
            
            suggestions = self.parser.parse_suggestions(response if isinstance(response, dict) else {})
            
            self.logger.info(f"Obtidas {len(suggestions)} sugestões", keyword=query)
            return suggestions
            
        except Exception as e:
            self.logger.erro(f"Erro ao obter sugestões: {e}")
            return []

    @debug_log(log_args=True, log_result=True, log_duration=True)
    def get_random(self, query: str) -> Optional[str]:
        """
        Obtém uma sugestão aleatória.
        
        Args:
            query: Palavra-chave para buscar sugestões
            
        Returns:
            Optional[str]: Sugestão aleatória ou None
        """
        suggestions = self.get_all(query)
        
        if not suggestions:
            self.logger.aviso(f"Nenhuma sugestão encontrada para: {query}")
            return None
        
        selected = random.choice(suggestions)
        
        self.logger.debug("Sugestão aleatória selecionada", keyword=query, suggestion=selected)
        
        return selected

    def _validate_keyword(self, keyword: str) -> None:
        """Valida a palavra-chave."""
        if not isinstance(keyword, str) or not keyword.strip():
            raise InvalidInputException(
                "Palavra-chave não pode ser vazia",
                details={"keyword": keyword, "type": type(keyword).__name__}
            )
    
    def _prepare_template(self, keyword: str) -> Dict[str, Any]:
        """Prepara template com a palavra-chave."""
        template_copy = self.load_and_copy_template(TEMPLATE_FILE)
        
        if "url" in template_copy and isinstance(template_copy["url"], str):
            template_copy["url"] = self.parser.update_url_with_query(
                template_copy["url"],
                keyword
            )
        
        return template_copy
