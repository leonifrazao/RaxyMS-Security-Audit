"""
Classe base para serviços.

Define funcionalidades comuns e padrões para todos os serviços.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from raxy.core.exceptions import (
    RaxyBaseException,
    wrap_exception,
)
from raxy.core.exceptions import (
    RaxyBaseException,
    wrap_exception,
)


class BaseService(ABC):
    """
    Classe base abstrata para todos os serviços.
    
    Fornece funcionalidades comuns como logging, tratamento
    de erros e validação.
    """
    
    def __init__(self, logger: Optional[Any] = None):
        """
        Inicializa o serviço.
        
        Args:
            logger: Serviço de logging (opcional)
        """
        self._logger = logger or self._get_default_logger()
        self._initialized = False
    
    def _get_default_logger(self) -> Any:
        """
        Obtém logger padrão se nenhum foi fornecido.
        
        Returns:
            Logger padrão
        """
        from raxy.core.logging import get_logger
        return get_logger()
    
    def initialize(self) -> None:
        """
        Inicializa o serviço.
        
        Deve ser chamado antes de usar o serviço.
        Pode ser sobrescrito pelas subclasses.
        """
        if self._initialized:
            return
        
        self._logger.debug(f"Inicializando {self.__class__.__name__}")
        
        try:
            self._initialize_impl()
            self._initialized = True
            self._logger.info(f"{self.__class__.__name__} inicializado com sucesso")
        except Exception as e:
            self._logger.erro(
                f"Erro ao inicializar {self.__class__.__name__}",
                exception=e
            )
            raise
    
    def _initialize_impl(self) -> None:
        """
        Implementação específica de inicialização.
        
        Deve ser sobrescrito pelas subclasses se necessário.
        """
        pass
    
    def validate_input(self, **kwargs: Any) -> None:
        """
        Valida inputs do serviço.
        
        Args:
            **kwargs: Inputs a validar
            
        Raises:
            ValidationException: Se validação falhar
        """
        for key, value in kwargs.items():
            if value is None:
                from raxy.core.exceptions import MissingRequiredFieldException
                raise MissingRequiredFieldException(f"Campo obrigatório: {key}")
    
    def handle_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """
        Trata erros de forma padronizada.
        
        Args:
            error: Erro ocorrido
            context: Contexto do erro
        """
        self._logger.erro(
            f"Erro em {self.__class__.__name__}",
            exception=error,
            **context
        )
        
        # Re-lança se for erro do Raxy
        if isinstance(error, RaxyBaseException):
            raise
        
        # Envolve em erro genérico
        raise wrap_exception(
            error,
            RaxyBaseException,
            f"Erro no serviço {self.__class__.__name__}",
            **context
        )
    
    @property
    def logger(self) -> Any:
        """Acesso ao logger do serviço."""
        return self._logger
    
    @property
    def is_initialized(self) -> bool:
        """Verifica se serviço foi inicializado."""
        return self._initialized
    
    def __repr__(self) -> str:
        """Representação string do serviço."""
        status = "initialized" if self._initialized else "not initialized"
        return f"{self.__class__.__name__}({status})"


class AsyncService(BaseService):
    """
    Base para serviços assíncronos.
    
    Adiciona suporte para operações assíncronas.
    """
    
    async def initialize_async(self) -> None:
        """
        Inicialização assíncrona do serviço.
        
        Deve ser usada ao invés de initialize() para serviços async.
        """
        if self._initialized:
            return
        
        self._logger.debug(f"Inicializando async {self.__class__.__name__}")
        
        try:
            await self._initialize_async_impl()
            self._initialized = True
            self._logger.info(f"{self.__class__.__name__} inicializado com sucesso (async)")
        except Exception as e:
            self._logger.erro(
                f"Erro ao inicializar async {self.__class__.__name__}",
                exception=e
            )
            raise
    
    async def _initialize_async_impl(self) -> None:
        """
        Implementação específica de inicialização assíncrona.
        
        Deve ser sobrescrito pelas subclasses se necessário.
        """
        pass
