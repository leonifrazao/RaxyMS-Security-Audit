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
import time
import string

from raxy.interfaces.services import IBingSuggestion, ILoggingService, ISessionManager, IRewardsDataService
from raxy.core.exceptions import (
    BingAPIException,
    InvalidAPIResponseException,
    InvalidInputException,
)
from raxy.core.config import get_config
from raxy.core.logging import debug_log
from .base_api import BaseAPIClient
from raxy.models.suggestion import Suggestion


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
        
    @debug_log(log_args=True, log_result=False, log_duration=True)
    def realizar_pesquisa(
        self,
        sessao: ISessionManager,
        termo: str,
        form_code: str = "QBLH",
        mobile: bool = False
    ) -> bool:
        """
        Realiza uma pesquisa no Bing.
        
        Args:
            sessao: Sessão do usuário
            termo: Termo a pesquisar
            form_code: Código da origem (form)
            mobile: Se deve realizar pesquisa mobile
            
        Returns:
            bool: True se sucesso, False caso contrário
        """
        try:
            # Carrega template
            template = self.load_template("realizar_pesquisa.json")
            
            # Realiza substituições manuais para garantir encoding correto
            import urllib.parse
            q_encoded = urllib.parse.quote(termo)
            
            # 1. URL
            if "url" in template and isinstance(template["url"], str):
                 template["url"] = template["url"].replace("{definir}", q_encoded).replace("{form}", form_code)
                 
            # 2. Headers (Referer)
            if "headers" in template and isinstance(template.get("headers"), dict):
                headers = template["headers"]
                if "Referer" in headers and isinstance(headers["Referer"], str):
                    headers["Referer"] = headers["Referer"].replace("{definir}", q_encoded).replace("{form}", form_code)
                
                # Fix: Update Client Hints for Mobile
                if mobile:
                    headers["sec-ch-ua-mobile"] = "?1"
                    headers["sec-ch-ua-platform"] = '"Android"' # Default safe assumption for mobile
                    # Remove conflicting desktop hints if present
                    if "sec-ch-ua-arch" in headers: del headers["sec-ch-ua-arch"]
                    if "sec-ch-ua-bitness" in headers: del headers["sec-ch-ua-bitness"]

                
            # 3. Data (Body) - Double Encoding may be required based on previous logic
            if "data" in template and isinstance(template["data"], str):
                 q_double_encoded = urllib.parse.quote(q_encoded)
                 template["data"] = template["data"].replace("{definir}", q_double_encoded).replace("{form}", form_code)

            # Executa requisição (sem placeholders pois já substituímos)
            response = sessao.execute_template(
                template,
                placeholders=None,
                mobile=mobile
            )
            
            # Valida resposta
            self._validate_response(response, context={
                "termo": termo, 
                "mobile": mobile
            })
            
            return True
            
        except Exception as e:
            self.logger.aviso(f"Erro ao realizar pesquisa '{termo}': {e}")
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
    

    def realizar_ciclo_pesquisa(
        self,
        sessao: ISessionManager,
        rewards_service: IRewardsDataService,
        mobile: bool = False
    ) -> bool:
        """
        Realiza ciclo completo de pesquisa (PC ou Mobile).
        
        Args:
            sessao: Sessão ativa
            rewards_service: Serviço de rewards para verificação de progresso
            mobile: Se True, realiza pesquisas mobile. Se False, PC.
            
        Returns:
            bool: True se completou com sucesso (ou já estava completo)
        """
        tipo = "Mobile" if mobile else "PC"
        self.logger.debug(f"Iniciando ciclo de pesquisa {tipo}...")
        
        try:
            # 1. Fetch inicial de progresso
            dashboard = rewards_service.obter_recompensas(sessao, bypass_request_token=True)
            
            if mobile:
                current, max_val = rewards_service.get_mobile_search_progress(dashboard)
            else:
                current, max_val = rewards_service.get_pc_search_progress(dashboard)
                
        except Exception as e:
            self.logger.aviso(f"Erro ao obter dashboard inicial ({tipo}): {e}")
            # Fallback seguro
            current, max_val = 0, 100 if mobile else 150
            
        # Verifica se já completou
        # Ajuste: se max_val for 0 (erro de parse ou API), assumimos que precisamos tentar
        last_valid_max = max_val if max_val > 0 else (100 if mobile else 150)
        
        if current >= last_valid_max:
            self.logger.info(f"Busca {tipo} já concluída: {current}/{last_valid_max}")
            return True
            
        # Loop de pesquisa
        attempts = 0
        searches_without_progress = 0
        
        while current < last_valid_max:
            attempts += 1
            
            # Gera query
            query = self._generate_search_query(sessao)
            form_code = self._get_random_form_code()
            
            self.logger.info(f"Busca {tipo} {attempts}: {current}/{last_valid_max} - Termo: '{query}'")
            
            # Executa
            success = self.realizar_pesquisa(sessao, query, form_code=form_code, mobile=mobile)
            
            if success:
                # Delay natural
                time.sleep(random.uniform(5.0, 7.0))
                searches_without_progress += 1
                
                # Verifica progresso
                # A cada 5 buscas ou se estiver perto do fim
                should_check = (searches_without_progress >= 5) or ((last_valid_max - current) <= 15)
                
                if should_check:
                    try:
                        dashboard = rewards_service.obter_recompensas(sessao, bypass_request_token=True)
                        if mobile:
                            new_curr, new_max = rewards_service.get_mobile_search_progress(dashboard)
                        else:
                            new_curr, new_max = rewards_service.get_pc_search_progress(dashboard)
                            
                        # Valida atualização
                        valid_update = True
                        if new_max == 0 and last_valid_max > 0:
                            valid_update = False # Ignora reset estranho
                            
                        if valid_update:
                            if new_curr > current:
                                current = new_curr
                                searches_without_progress = 0 # Reset stuck counter
                            
                            if new_max > 0:
                                last_valid_max = new_max
                                
                        if searches_without_progress >= 5:
                            self.logger.aviso(f"Sem progresso após 5 buscas ({tipo}). Interrompendo.")
                            break
                            
                    except Exception as e:
                        self.logger.aviso(f"Erro verificando progresso: {e}")
            else:
                self.logger.aviso(f"Falha na requisição ({tipo})")
                time.sleep(5)
                
        self.logger.info(f"Ciclo {tipo} finalizado. {current}/{last_valid_max}")
        return True

    def _generate_search_query(self, sessao: ISessionManager) -> str:
        """Gera uma query de pesquisa única e natural."""
        try:
            # Tenta usar wonderwords se disponível
            try:
                from wonderwords import RandomWord
                r = RandomWord()
                seed = r.word()
            except ImportError:
                # Fallback se lib não existe
                seed = ''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 8)))
                
            # Obtém sugestões para naturalidade
            suggestions = self.get_all(sessao, seed)
            
            if suggestions:
                return random.choice(suggestions).text
            
            return f"{seed} {random.randint(100, 999)}"
                
        except Exception:
            # Fallback final
            return f"search {random.randint(1, 10000)}"

    def _get_random_form_code(self) -> str:
        """Retorna código FORM aleatório."""
        forms = ["QBLH", "QBRE", "HDRSC1", "LGWQS1", "R5FD", "QSRE1"]
        return random.choice(forms)
