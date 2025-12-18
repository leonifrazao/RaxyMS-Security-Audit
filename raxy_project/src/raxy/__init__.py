"""
Raxy - Microsoft Rewards Automation Framework

Reorganized with Clean Architecture:
- core/domain: Business entities (Conta, Proxy, Session, etc.)
- core/services: Business logic (SessionManager, ExecutorService)
- core/exceptions: Custom exception hierarchy
- adapters/api: External API clients (Bing, MailTM, Rewards)
- adapters/repositories: Data persistence
- infrastructure: Config, Logging, HTTP clients
"""

from raxy.core.domain import (
    Conta,
    Proxy,
    SessionState,
    EtapaResult,
    ContaResult,
)

from raxy.core.exceptions import (
    RaxyBaseException,
    SessionException,
    LoginException,
    ProxyRotationRequiredException,
)

__version__ = "2.0.0"

__all__ = [
    # Domain
    "Conta",
    "Proxy",
    "SessionState",
    "EtapaResult",
    "ContaResult",
    # Exceptions
    "RaxyBaseException",
    "SessionException",
    "LoginException",
    "ProxyRotationRequiredException",
    # Version
    "__version__",
]
