"""
Classe base para clientes de API.
"""

from __future__ import annotations

import json
from abc import ABC
from typing import Any, Dict, Optional, List

from raxy.interfaces.services import ILoggingService


class BaseAPIClient(ABC):
    """
    Classe base para clientes de API.
    
    Fornece funcionalidades comuns:
    - Carregamento de templates JSON
    - Logger
    - Configurações básicas (base_url, timeout, error_words)
    
    As requisições HTTP devem usar SessionManager.execute_template()
    que já gerencia cookies, UA, proxy e retry.
    """
    

    def __init__(
        self,
        logger: Optional[ILoggingService] = None,
        timeout: int = 30,
        error_words: Optional[List[str]] = None,
    ):
        """
        Inicializa o cliente de API.
        
        Args:
            logger: Logger (opcional)
            timeout: Timeout em segundos
            error_words: Palavras que indicam erro na resposta
        """
        self._logger = logger or self._get_logger()
        self.timeout = timeout
        self.error_words = tuple(word.lower() for word in (error_words or []))
    
    def _get_logger(self) -> ILoggingService:
        """Obtém logger padrão."""
        from raxy.core.logging import get_logger
        return get_logger()
    
    def load_template(self, template_name: str) -> Dict[str, Any]:
        """Carrega template JSON."""
        from raxy.core.config import get_config
        templates_dir = get_config().templates_dir
        
        with open(templates_dir / template_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @property
    def logger(self) -> ILoggingService:
        """Logger."""
        return self._logger

    def _execute_request(
        self,
        sessao: Any, # Typed as Any to avoid circular import with ISessionManager if not careful, but ideally should be ISessionManager
        template: Dict[str, Any],
        bypass_request_token: bool = True,
        error_context: Optional[str] = None
    ) -> Any:
        """
        Executa uma requisição usando o template.
        
        Args:
            sessao: Sessão do usuário
            template: Template de requisição
            bypass_request_token: Se deve bypass do token
            error_context: Contexto para erro (opcional)
            
        Returns:
            Response: Resposta da requisição
            
        Raises:
            Exception: Se erro na execução (envolvido por wrap_exception se possível)
        """
        try:
            return sessao.execute_template(
                template,
                bypass_request_token=bypass_request_token
            )
        except Exception as e:
            # Import aqui para evitar circularidade se necessário, 
            # ou assumir que Exception types e wrap_exception estão disponíveis
            from raxy.core.exceptions import wrap_exception, RaxyBaseException
            
            # Se já for RaxyBaseException, deixa propagar ou envolve?
            # O ideal é envolver num tipo genérico de API ou deixar o caller tratar.
            # Aqui vamos deixar propagar exception "crua" mas logada, 
            # ou melhor, deixar o caller fazer o wrap específico com o tipo de exceção da API (ex: RewardsAPIException)
            # Mas para facilitar, vamos lançar e o caller captura.
            raise e

    def _validate_response(
        self,
        response: Any,
        context: Optional[Dict[str, Any]] = None,
        check_error_words: bool = True
    ) -> None:
        """
        Valida a resposta da API.
        
        Args:
            response: Objeto de resposta
            context: Contexto para detalhes do erro
            check_error_words: Se deve verificar palavras de erro no corpo
            
        Raises:
            InvalidAPIResponseException: Se status != 2xx ou palavras de erro encontradas
        """
        from raxy.core.exceptions import InvalidAPIResponseException, APIException
        
        status = getattr(response, "status_code", None)
        ok = getattr(response, "ok", False)
        
        if not ok:
            raise InvalidAPIResponseException(
                f"Request falhou com status {status}",
                details={"status_code": status, **(context or {})}
            )
            
        if check_error_words and self.error_words:
            text = getattr(response, "text", "")
            if text:
                text_lower = text.lower()
                for word in self.error_words:
                    if word in text_lower:
                        raise APIException(
                            f"Resposta contém termo de erro: {word}",
                            details={
                                "error_word": word,
                                "preview": text[:200],
                                **(context or {})
                            }
                        )

    def _parse_json(
        self,
        response: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Decodifica resposta JSON de forma segura.
        
        Args:
            response: Objeto de resposta
            context: Contexto para erro
            
        Returns:
            Any: Dados decodificados
            
        Raises:
            JSONParsingException: Se falha ao decodificar
        """
        from raxy.core.exceptions import JSONParsingException, wrap_exception
        
        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise wrap_exception(
                e, JSONParsingException,
                "Erro ao decodificar resposta JSON",
                status_code=getattr(response, "status_code", None),
                **(context or {})
            )

    def execute_template_and_parse(
        self,
        sessao: Any,
        template: Dict[str, Any],
        bypass_request_token: bool = True,
        check_error_words: bool = True,
        exception_type: type = Exception,
        error_message: str = "Erro na requisição API",
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Método utilitário completo: executa -> valida -> parseia JSON.
        
        Args:
            sessao: Sessão do usuário
            template: Template de requisição
            bypass_request_token: Bypass token
            check_error_words: Verificar palavras de erro
            exception_type: Tipo de exceção para envolver erros (ex: RewardsAPIException)
            error_message: Mensagem base para erros
            context: Dados extras para erro
            
        Returns:
            Any: Dados JSON parseados
            
        Raises:
            exception_type: Se qualquer erro ocorrer
        """
        from raxy.core.exceptions import wrap_exception
        
        try:
            # 1. Executa
            response = self._execute_request(sessao, template, bypass_request_token)
            
            # 2. Valida
            self._validate_response(response, context, check_error_words)
            
            # 3. Parse JSON
            return self._parse_json(response, context)
            
        except Exception as e:
            # Log exception details before wrapping
            self.logger.erro(f"Erro em execute_template_and_parse ({error_message})", exception=e, context=context)
            
            # Evita envolver exceptions que já são do tipo correto ou RaxyBaseException se o caller quiser
            # Mas wrap_exception lida bem com isso normalmente se configurado.
            # Aqui, forçamos o wrap para o tipo específico da API para manter consistência
            raise wrap_exception(
                e, exception_type,
                error_message,
                **(context or {})
            )

