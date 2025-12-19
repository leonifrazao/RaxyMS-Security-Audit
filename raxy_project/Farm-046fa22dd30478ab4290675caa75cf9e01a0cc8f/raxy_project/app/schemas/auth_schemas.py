"""Schemas relacionados à autenticação."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    """Dados necessários para autenticar uma conta Rewards."""
    
    email: str = Field(..., description="Email da conta")
    password: str = Field(..., description="Senha da conta")
    profile_id: Optional[str] = Field(None, description="Perfil a ser utilizado; default usa o email")
    proxy: Optional[Dict[str, Any]] = Field(None, description="Configuração de proxy opcional")


class AuthResponse(BaseModel):
    """Dados retornados após autenticação bem sucedida."""
    
    status: str = "authenticated"
    session_id: str
    profile_id: str
    email: str


class SessionCloseRequest(BaseModel):
    """Requisição para fechar uma sessão."""
    
    session_id: str = Field(..., description="ID da sessão a ser fechada")
