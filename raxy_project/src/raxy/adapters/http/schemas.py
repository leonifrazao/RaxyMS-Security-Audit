"""Schemas da API - Modelos Pydantic para requests e responses."""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel


# ==================== Account ====================

class AccountSource(str, Enum):
    FILE = "file"
    DATABASE = "database"


class AccountResponse(BaseModel):
    email: str
    profile_id: str
    password: Optional[str] = None
    proxy: Optional[str] = None
    source: AccountSource = AccountSource.FILE


class AccountsResponse(BaseModel):
    accounts: List[AccountResponse] = []


# ==================== Auth ====================

class LoginRequest(BaseModel):
    email: str
    password: str
    profile_id: Optional[str] = None


class LoginResponse(BaseModel):
    session_id: str
    email: str
    status: str
    message: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    email: str
    status: str


# ==================== Proxy ====================

class ProxyResponse(BaseModel):
    id: str
    url: str
    status: str = "available"


class ProxiesResponse(BaseModel):
    proxies: List[ProxyResponse] = []


class ProxyTestRequest(BaseModel):
    threads: Optional[int] = 10
    country: Optional[str] = None
    timeout: Optional[float] = 10.0
    force: Optional[bool] = False
    find_first: Optional[int] = None


class ProxyTestResponse(BaseModel):
    tested: int
    working: int
    message: str


class ProxyRotateRequest(BaseModel):
    bridge_id: int


# ==================== Rewards ====================

class RewardsDataRequest(BaseModel):
    session_id: Optional[str] = None


class RewardsDataResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, Any] = {}


# ==================== Suggestions ====================

class SuggestionRequest(BaseModel):
    query: str


class SuggestionResponse(BaseModel):
    query: str
    suggestions: List[str] = []
    success: bool = True
    error: Optional[str] = None


# ==================== Logging ====================

class LogRequest(BaseModel):
    level: str = "info"
    message: str
    extra: Optional[Dict[str, Any]] = None


class LogResponse(BaseModel):
    success: bool
    message: str


# ==================== Flyout ====================

class FlyoutRequest(BaseModel):
    session_id: Optional[str] = None
    action: Optional[str] = None


class FlyoutResponse(BaseModel):
    success: bool
    message: str


# ==================== MailTM ====================

class MailTmAccountRequest(BaseModel):
    address: Optional[str] = None
    password: Optional[str] = None


class MailTmAccountResponse(BaseModel):
    success: bool
    email: str
    token: str
    message: str


class MailTmMessagesResponse(BaseModel):
    success: bool
    messages: List[Dict[str, Any]] = []
    error: Optional[str] = None


# ==================== Executor ====================

class ExecutorRequest(BaseModel):
    emails: Optional[List[str]] = None
    actions: Optional[List[str]] = None


class ExecutorResponse(BaseModel):
    success: bool
    message: str
    processed: int = 0


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: Optional[str] = None
    result: Optional[Any] = None
    message: Optional[str] = None


__all__ = [
    # Account
    "AccountSource",
    "AccountResponse",
    "AccountsResponse",
    # Auth
    "LoginRequest",
    "LoginResponse",
    "SessionResponse",
    # Proxy
    "ProxyResponse",
    "ProxiesResponse",
    "ProxyTestRequest",
    "ProxyTestResponse",
    "ProxyRotateRequest",
    # Rewards
    "RewardsDataRequest",
    "RewardsDataResponse",
    # Suggestions
    "SuggestionRequest",
    "SuggestionResponse",
    # Logging
    "LogRequest",
    "LogResponse",
    # Flyout
    "FlyoutRequest",
    "FlyoutResponse",
    # MailTM
    "MailTmAccountRequest",
    "MailTmAccountResponse",
    "MailTmMessagesResponse",
    # Executor
    "ExecutorRequest",
    "ExecutorResponse",
    "JobStatusResponse",
]