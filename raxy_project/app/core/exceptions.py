"""Exceções customizadas para a API."""

from fastapi import HTTPException
from typing import Any, Dict, Optional


class APIException(HTTPException):
    """Exceção base para a API."""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class NotFoundError(APIException):
    """Recurso não encontrado (404)."""
    
    def __init__(self, resource: str = "Recurso"):
        super().__init__(
            status_code=404,
            detail=f"{resource} não encontrado"
        )


class ValidationError(APIException):
    """Erro de validação (400)."""
    
    def __init__(self, field: str, message: str):
        super().__init__(
            status_code=400,
            detail=f"Erro de validação no campo '{field}': {message}"
        )


class UnauthorizedError(APIException):
    """Erro de autorização (401)."""
    
    def __init__(self, detail: str = "Não autorizado"):
        super().__init__(status_code=401, detail=detail)


class ConflictError(APIException):
    """Erro de conflito (409)."""
    
    def __init__(self, detail: str = "Conflito ao processar requisição"):
        super().__init__(status_code=409, detail=detail)


class ServiceUnavailableError(APIException):
    """Serviço indisponível (503)."""
    
    def __init__(self, service: str = "Serviço"):
        super().__init__(
            status_code=503,
            detail=f"{service} temporariamente indisponível"
        )
