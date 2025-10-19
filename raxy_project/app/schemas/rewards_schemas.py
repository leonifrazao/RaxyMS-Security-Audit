"""Schemas relacionados a rewards."""

from __future__ import annotations

from typing import Any, Dict
from pydantic import BaseModel, Field


class RewardsPointsRequest(BaseModel):
    """Requisição para obter pontos de rewards."""
    
    session_id: str = Field(..., description="ID da sessão autenticada")
    bypass_request_token: bool = Field(True, description="Bypass do request token")


class RewardsRedeemRequest(BaseModel):
    """Requisição para resgatar rewards."""
    
    session_id: str = Field(..., description="ID da sessão autenticada")
    bypass_request_token: bool = Field(True, description="Bypass do request token")


class RewardsResponse(BaseModel):
    """Resposta de operação de rewards."""
    
    status: str
    data: Dict[str, Any]
