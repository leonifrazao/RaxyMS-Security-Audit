"""Schemas relacionados a sugestões."""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class SuggestionRequest(BaseModel):
    """Requisição para obter sugestões."""
    
    session_id: str = Field(..., description="ID da sessão autenticada")
    keyword: str = Field(..., description="Palavra-chave para buscar sugestões")


class SuggestionResponse(BaseModel):
    """Resposta com sugestões."""
    
    status: str
    total: int
    suggestions: List[Dict[str, Any]]
