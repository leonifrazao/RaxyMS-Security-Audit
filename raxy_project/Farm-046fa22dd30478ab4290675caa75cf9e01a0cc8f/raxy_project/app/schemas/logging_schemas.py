"""Schemas relacionados a logging."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class LoggingMessageRequest(BaseModel):
    """Requisição para registrar mensagem de log."""
    
    session_id: Optional[str] = Field(None, description="Opcionalmente associa a um contexto de sessão")
    level: str = Field(..., description="Nível do log (debug, info, sucesso, aviso, erro, critico)")
    message: str = Field(..., description="Mensagem a ser registrada")
    extra: Optional[Dict[str, Any]] = Field(None, description="Dados adicionais do log")


class LoggingOperationResponse(BaseModel):
    """Resposta de operação de logging."""
    
    status: str
    level: str
