"""Respostas padronizadas da API."""

from typing import Any, Dict, Optional
from pydantic import BaseModel


class APIResponse(BaseModel):
    """Resposta base da API."""
    
    status: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    

class SuccessResponse(APIResponse):
    """Resposta de sucesso."""
    
    def __init__(self, message: str = "Operação realizada com sucesso", data: Optional[Dict[str, Any]] = None):
        super().__init__(status="success", message=message, data=data)


class ErrorResponse(APIResponse):
    """Resposta de erro."""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(
            status="error",
            message=message,
            data={"error_code": error_code} if error_code else None
        )


class PaginatedResponse(BaseModel):
    """Resposta paginada."""
    
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    @classmethod
    def from_items(cls, items: list, page: int = 1, page_size: int = 20) -> "PaginatedResponse":
        """Cria resposta paginada a partir de lista de itens."""
        total = len(items)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        return cls(
            items=items[start_idx:end_idx],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size
        )
