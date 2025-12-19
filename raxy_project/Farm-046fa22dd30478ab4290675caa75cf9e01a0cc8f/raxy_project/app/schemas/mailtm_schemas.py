"""Schemas relacionados ao MailTM."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MailTmCreateAccountRequest(BaseModel):
    """Requisição para criar conta MailTM."""
    
    address: Optional[str] = Field(None, description="Endereço de email desejado (sem random)")
    password: Optional[str] = Field(None, description="Senha para a conta")
    random: bool = Field(True, description="Se True, cria conta com endereço aleatório")


class MailTmCreateAccountResponse(BaseModel):
    """Resposta de criação de conta MailTM."""
    
    address: str
    password: str
    token: str


class MailTmGetDomainsResponse(BaseModel):
    """Resposta com domínios disponíveis."""
    
    domains: List[str]


class MailTmGetMessagesResponse(BaseModel):
    """Resposta com lista de mensagens."""
    
    messages: List[Dict[str, Any]]


class MailTmGetMessageResponse(BaseModel):
    """Resposta com detalhes de uma mensagem."""
    
    message: Dict[str, Any]
