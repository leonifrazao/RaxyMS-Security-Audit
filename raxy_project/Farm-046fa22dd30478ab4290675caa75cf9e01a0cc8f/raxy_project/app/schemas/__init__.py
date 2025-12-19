"""Módulo de schemas da API."""

from .account_schemas import (
    AccountSource,
    AccountPayload,
    AccountResponse,
    AccountsResponse,
)
from .auth_schemas import (
    AuthRequest,
    AuthResponse,
    SessionCloseRequest,
)
from .proxy_schemas import (
    ProxySourcesRequest,
    ProxyAddRequest,
    ProxyStartRequest,
    ProxyTestRequest,
    ProxyRotateRequest,
    ProxyOperationResponse,
)
from .rewards_schemas import (
    RewardsPointsRequest,
    RewardsRedeemRequest,
    RewardsResponse,
)
from .suggestion_schemas import (
    SuggestionRequest,
    SuggestionResponse,
)
from .logging_schemas import (
    LoggingMessageRequest,
    LoggingOperationResponse,
)
from .executor_schemas import (
    ExecutorBatchRequest,
    ExecutorBatchResponse,
)
from .flyout_schemas import (
    FlyoutExecuteRequest,
    FlyoutExecuteResponse,
)
from .mailtm_schemas import (
    MailTmCreateAccountRequest,
    MailTmCreateAccountResponse,
    MailTmGetDomainsResponse,
    MailTmGetMessagesResponse,
    MailTmGetMessageResponse,
)

__all__ = [
    # Account
    "AccountSource",
    "AccountPayload",
    "AccountResponse",
    "AccountsResponse",
    # Auth
    "AuthRequest",
    "AuthResponse",
    "SessionCloseRequest",
    # Proxy
    "ProxySourcesRequest",
    "ProxyAddRequest",
    "ProxyStartRequest",
    "ProxyTestRequest",
    "ProxyRotateRequest",
    "ProxyOperationResponse",
    # Rewards
    "RewardsPointsRequest",
    "RewardsRedeemRequest",
    "RewardsResponse",
    # Suggestion
    "SuggestionRequest",
    "SuggestionResponse",
    # Logging
    "LoggingMessageRequest",
    "LoggingOperationResponse",
    # Executor
    "ExecutorBatchRequest",
    "ExecutorBatchResponse",
    # Flyout
    "FlyoutExecuteRequest",
    "FlyoutExecuteResponse",
    # MailTM
    "MailTmCreateAccountRequest",
    "MailTmCreateAccountResponse",
    "MailTmGetDomainsResponse",
    "MailTmGetMessagesResponse",
    "MailTmGetMessageResponse",
]
