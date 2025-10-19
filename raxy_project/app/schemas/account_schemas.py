"""Schemas relacionados a contas."""

from __future__ import annotations

from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class AccountSource(str, Enum):
    """Origem das contas."""
    FILE = "file"
    DATABASE = "database"
    MANUAL = "manual"


class AccountPayload(BaseModel):
    """Payload de uma conta."""
    
    email: str = Field(..., description="Email da conta")
    password: str = Field(..., description="Senha da conta")
    profile_id: Optional[str] = Field(None, description="Perfil a ser utilizado durante a execução")
    proxy: Optional[str] = Field(None, description="URI de proxy opcional")


class AccountResponse(BaseModel):
    """Resposta com dados de uma conta."""
    
    email: str
    profile_id: str
    password: Optional[str] = Field(
        None,
        description="Senha associada à conta quando disponível (arquivo ou banco)"
    )
    proxy: Optional[str] = None
    source: AccountSource


class AccountsResponse(BaseModel):
    """Resposta com lista de contas."""
    
    accounts: List[AccountResponse]
