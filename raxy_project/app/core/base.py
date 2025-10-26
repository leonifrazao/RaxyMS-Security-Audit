"""Base controller com funcionalidades comuns."""

from __future__ import annotations

from typing import Any, Optional
from fastapi import Request, HTTPException
import logging


class BaseController:
    """
    Classe base para todos os controllers da API.
    
    Fornece funcionalidades comuns como:
    - Logging padronizado
    - Tratamento de erros
    - Validação de entrada
    - Métodos utilitários
    """
    
    def __init__(self):
        """Inicializa o controller com logger configurado."""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def validate_session_id(self, session_id: str) -> None:
        """
        Valida o formato do session_id.
        
        Args:
            session_id: ID da sessão a validar
            
        Raises:
            HTTPException: Se o session_id for inválido
        """
        if not session_id or not session_id.strip():
            raise HTTPException(status_code=400, detail="session_id é obrigatório")
    
    def handle_service_error(self, error: Exception, context: str = "") -> None:
        """
        Trata erros de serviço de forma padronizada.
        
        Args:
            error: Exceção capturada
            context: Contexto adicional do erro
            
        Raises:
            HTTPException: Com detalhes apropriados do erro
        """
        self.logger.erro(f"Erro em {context}: {str(error)}", exc_info=True)
        
        # Mapeia exceções conhecidas
        error_mapping = {
            "SessionNotFound": (404, "Sessão não encontrada"),
            "InvalidCredentials": (401, "Credenciais inválidas"),
            "ProxyError": (503, "Erro de proxy"),
            "TimeoutError": (408, "Timeout na operação"),
        }
        
        error_name = error.__class__.__name__
        status_code, detail = error_mapping.get(
            error_name, 
            (500, f"Erro interno: {str(error)}")
        )
        
        raise HTTPException(status_code=status_code, detail=detail)
    
    def log_request(self, endpoint: str, params: Optional[dict] = None) -> None:
        """
        Registra detalhes da requisição.
        
        Args:
            endpoint: Nome do endpoint
            params: Parâmetros da requisição
        """
        self.logger.info(
            f"Request: {endpoint}",
            extra={"params": params} if params else {}
        )
    
    def log_response(self, endpoint: str, response: Any) -> None:
        """
        Registra detalhes da resposta.
        
        Args:
            endpoint: Nome do endpoint
            response: Dados da resposta
        """
        self.logger.debug(
            f"Response: {endpoint}",
            extra={"response": response}
        )
    
    def get_injector(self, request: Request):
        """
        Obtém o injector do estado da aplicação.
        
        Args:
            request: Objeto Request do FastAPI
            
        Returns:
            SimpleInjector: Instância do injector
            
        Raises:
            RuntimeError: Se o injector não estiver disponível
        """
        from raxy.core.exceptions import ContainerException
        
        injector = getattr(request.app.state, "injector", None)
        if injector is None:
            raise ContainerException("Container de dependências não foi inicializado")
        return injector
    
    def get_session_store(self, request: Request) -> dict:
        """
        Obtém o armazenamento de sessões.
        
        Args:
            request: Objeto Request do FastAPI
            
        Returns:
            Dict: Dicionário de sessões
        """
        store = getattr(request.app.state, "sessions", None)
        if store is None:
            store = {}
            request.app.state.sessions = store
        return store
