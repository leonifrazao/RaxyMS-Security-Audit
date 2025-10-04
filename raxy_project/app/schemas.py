"""Modelos Pydantic expostos pela camada de API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ProfileEnsureRequest(BaseModel):
    """Representa uma solicitação para garantir a existência de um perfil."""

    profile_id: str = Field(..., description="Identificador único do perfil.")
    email: str = Field(..., description="Email associado ao perfil.")
    password: str = Field(..., description="Senha associada ao email.")




class AccountSource(str, Enum):
    FILE = "file"
    DATABASE = "database"
    MANUAL = "manual"


class AccountPayload(BaseModel):
    email: str
    password: str
    profile_id: Optional[str] = Field(None, description="Perfil a ser utilizado durante a execução.")
    proxy: Optional[str] = Field(None, description="URI de proxy opcional.")


class AccountResponse(BaseModel):
    email: str
    profile_id: str
    password: Optional[str] = Field(
        None,
        description="Senha associada à conta quando disponível (arquivo ou banco).",
    )
    proxy: Optional[str] = None
    source: AccountSource


class AccountsResponse(BaseModel):
    accounts: List[AccountResponse]

class ProfileEnsureResponse(BaseModel):
    status: str = "success"
    profile_id: str


class AuthRequest(BaseModel):
    """Dados necessários para autenticar uma conta Rewards."""

    email: str
    password: str
    profile_id: Optional[str] = Field(None, description="Perfil a ser utilizado; default usa o email.")
    proxy: Optional[Dict[str, Any]] = Field(None, description="Configuração de proxy opcional.")


class AuthResponse(BaseModel):
    """Dados retornados após autenticação bem sucedida."""

    status: str = "authenticated"
    session_id: str
    profile_id: str
    email: str


class SessionCloseRequest(BaseModel):
    session_id: str


class ProxySourcesRequest(BaseModel):
    sources: List[str]


class ProxyAddRequest(BaseModel):
    proxies: List[str]


class ProxyStartRequest(BaseModel):
    threads: Optional[int] = None
    amounts: Optional[int] = None
    country: Optional[str] = None
    auto_test: bool = True
    wait: bool = False


class ProxyTestRequest(BaseModel):
    threads: Optional[int] = None
    country: Optional[str] = None
    verbose: Optional[bool] = None
    force_refresh: bool = False
    timeout: float = 10.0
    force: bool = False


class ProxyRotateRequest(BaseModel):
    bridge_id: int


class ProxyOperationResponse(BaseModel):
    status: str
    detail: Optional[str] = None


class RewardsPointsRequest(BaseModel):
    session_id: str
    bypass_request_token: bool = True


class RewardsRedeemRequest(BaseModel):
    session_id: str
    bypass_request_token: bool = True


class RewardsResponse(BaseModel):
    status: str
    data: Dict[str, Any]


class SuggestionRequest(BaseModel):
    session_id: str
    keyword: str


class SuggestionResponse(BaseModel):
    status: str
    total: int
    suggestions: List[Dict[str, Any]]


class LoggingMessageRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Opcionalmente associa a um contexto de sessão.")
    level: str = Field(..., description="Nível do log (debug, info, sucesso, aviso, erro, critico).")
    message: str
    extra: Dict[str, Any] | None = None


class LoggingOperationResponse(BaseModel):
    status: str
    level: str


class ExecutorBatchRequest(BaseModel):
    actions: Optional[List[str]] = Field(None, description="Ações específicas a executar; usa padrão se ausente.")
    source: Optional[AccountSource] = Field(None, description="Origem das contas: file, database ou manual.")
    accounts: Optional[List[AccountPayload]] = Field(None, description="Lista de contas para execução manual.")
    account: Optional[AccountPayload] = Field(None, description="Conta individual para execução manual.")

    def manual_accounts(self) -> List[AccountPayload]:
        if self.accounts:
            return self.accounts
        if self.account:
            return [self.account]
        return []


class ExecutorBatchResponse(BaseModel):
    status: str
    detail: str
    source: AccountSource
