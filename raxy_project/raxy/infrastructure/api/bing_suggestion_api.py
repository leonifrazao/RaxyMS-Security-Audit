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

from raxy.interfaces.services import IBingSuggestion, ILoggingService, ISessionManager
from raxy.core.exceptions import (
    BingAPIException,
    InvalidAPIResponseException,
    InvalidInputException,
)
from raxy.core.config import get_config
from raxy.core.logging import debug_log
from .base_api import BaseAPIClient
from raxy.domain.suggestion import Suggestion


class SuggestionParser:
    """Parser para respostas de sugestões."""
    
    @staticmethod
    def parse_suggestions(response_data: Dict[str, Any]) -> List[Suggestion]:
        """
        Extrai sugestões da resposta.
        
        Args:
            response_data: Dados da resposta
            
        Returns:
            List[Suggestion]: Lista de sugestões
            
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
        
        result: List[Suggestion] = []
        for s in suggestions:
            if isinstance(s, dict):
                text = s.get("q")
                if text:
                    result.append(Suggestion(text=text, metadata=s))
            # Fallback se for string (improvável na API do Bing mas seguro)
            elif isinstance(s, str) and s.strip():
                result.append(Suggestion(text=s, metadata={}))
                
        return result
    
    @staticmethod
    def update_url_with_query(url: str, query: str, param_name: str) -> str:
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
            
            query_updated = False
            for i, (key, _) in enumerate(params):
                if key == param_name:
                    params[i] = (key, query)
                    query_updated = True
                    break
            
            if not query_updated:
                params.append((param_name, query))
            
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
        palavras_erro: Optional[Sequence[str]] = None,
    ):
        """
        Inicializa o cliente de sugestões.
        
        Args:
            logger: Serviço de logging
            palavras_erro: Palavras que indicam erro na resposta
        """
        config = get_config()
        super().__init__(
            logger=logger,
            error_words=palavras_erro or config.api.bing_suggestion_error_words
        )
        
        self.parser = SuggestionParser()

    @debug_log(log_args=True, log_result=False, log_duration=True)
    def get_all(
        self,
        sessao: ISessionManager,
        query: str,
        *,
        country: Optional[str] = None,
    ) -> Sequence[Suggestion]:
        """
        Obtém todas as sugestões para uma palavra-chave.
        
        Args:
            sessao: Sessão do usuário
            query: Palavra-chave para buscar sugestões
            
        Returns:
            Sequence[Suggestion]: Lista de sugestões
            
        Raises:
            InvalidInputException: Se entrada inválida
            BingAPIException: Se erro na API
        """
        
        # Valida entrada
        self._validate_keyword(query)
        
        self.logger.debug(f"Obtendo sugestões para: {query}")
        
        # Carrega e prepara template
        template = self._prepare_template(query.strip())
        
        # Executa, valida e parseia usando método base
        response_data = self.execute_template_and_parse(
            sessao=sessao,
            template=template,
            bypass_request_token=False,
            check_error_words=True,
            exception_type=BingAPIException,
            error_message="Erro ao obter sugestões",
            context={"keyword": query}
        )
        
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
        sessao: ISessionManager,
        keyword: str,
        *,
        country: Optional[str] = None,
    ) -> Optional[Suggestion]:
        """
        Obtém uma sugestão aleatória.
        
        Args:
            sessao: Sessão do usuário
            query: Palavra-chave para buscar sugestões
            
        Returns:
            Optional[Suggestion]: Sugestão aleatória
            
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
            suggestion=selected.text
        )
        
    @debug_log(log_args=True, log_result=True, log_duration=True)
    def realizar_pesquisa(
        self,
        sessao: ISessionManager,
        query: str,
        **kwargs
    ) -> bool:
        """
        Realiza uma pesquisa no Bing para pontuar.
        
        Args:
            sessao: Sessão do usuário
            query: Termo da pesquisa
            
        Returns:
            bool: True se sucesso, False caso contrário
        """
        self._validate_keyword(query)
        self.logger.debug(f"Realizando pesquisa bing: {query}")
        
        try:
            # Carrega template
            template_name = get_config().api.bing_suggestion.template_realizar_pesquisa
            template = self.load_template(template_name)
            
            # Substituições
            # Substituições
            form_val = kwargs.get("form_code", "QBRE")

            # 1. URL
            if "url" in template and isinstance(template["url"], str):
                 import urllib.parse
                 q_encoded = urllib.parse.quote(query)
                 template["url"] = template["url"].replace("{definir}", q_encoded).replace("{form}", form_val)
                 
            # 2. Headers
            if "headers" in template and "Referer" in template["headers"]:
                import urllib.parse
                q_encoded = urllib.parse.quote(query)
                template["headers"]["Referer"] = template["headers"]["Referer"].replace("{definir}", q_encoded).replace("{form}", form_val)
                
            # 3. Data
            if "data" in template:
                if isinstance(template["data"], dict) and "url" in template["data"]:
                    template["data"]["url"] = template["data"]["url"].replace("{definir}", query).replace("{form}", form_val)
                elif isinstance(template["data"], str):
                    # Codifica query DUPLAMENTE para o corpo (que contém URL encoded)
                    # Ex: 'siria cara' -> 'siria%20cara' -> 'siria%2520cara'
                    import urllib.parse
                    q_encoded = urllib.parse.quote(query)
                    q_double_encoded = urllib.parse.quote(q_encoded)
                    template["data"] = template["data"].replace("{definir}", q_double_encoded).replace("{form}", form_val)

            # Executa
            self._execute_request(
                sessao,
                template,
                bypass_request_token=False, 
                error_context=f"search={query}"
            )
            return True

        except Exception as e:
            self.logger.erro(f"Erro ao realizar pesquisa '{query}': {e}")
            return False

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
        template = self.load_template(get_config().api.bing_suggestion.template_file)
        
        # Faz cópia profunda para não modificar original
        template_copy = deepcopy(template)
        
        # Atualiza URL com query
        if "url" in template_copy and isinstance(template_copy["url"], str):
            template_copy["url"] = self.parser.update_url_with_query(
                template_copy["url"],
                keyword,
                get_config().api.bing_suggestion.query_param
            )
        
        return template_copy
    

