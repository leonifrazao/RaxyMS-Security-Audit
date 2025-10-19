"""Schemas relacionados ao executor."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from .account_schemas import AccountSource, AccountPayload


class ExecutorBatchRequest(BaseModel):
    """Requisição para execução em lote."""
    
    actions: List[str] = Field(..., description="Ações específicas a executar")
    source: Optional[AccountSource] = Field(None, description="Origem das contas: file, database ou manual")
    accounts: Optional[List[AccountPayload]] = Field(None, description="Lista de contas para execução manual")
    account: Optional[AccountPayload] = Field(None, description="Conta individual para execução manual")
    
    def manual_accounts(self) -> List[AccountPayload]:
        """Retorna contas manuais configuradas."""
        if self.accounts:
            return self.accounts
        if self.account:
            return [self.account]
        return []


class ExecutorBatchResponse(BaseModel):
    """Resposta de execução em lote."""
    
    status: str
    detail: str
    source: AccountSource
