"""Schemas relacionados ao flyout."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FlyoutExecuteRequest(BaseModel):
    """Requisição para executar flyout."""
    
    session_id: str = Field(..., description="ID da sessão autenticada")


class FlyoutExecuteResponse(BaseModel):
    """Resposta de execução do flyout."""
    
    status: str
    detail: str
    session_id: str
