"""Domain entities for the Raxy project."""

from raxy.core.domain.accounts import Conta
from raxy.core.domain.proxy import Proxy
from raxy.core.domain.session import SessionState
from raxy.core.domain.execution import EtapaResult, ContaResult
from raxy.core.domain.mailtm import Domain, Account, AuthenticatedSession, MessageAddress, Message

__all__ = [
    "Conta",
    "Proxy", 
    "SessionState",
    "EtapaResult",
    "ContaResult",
    "Domain",
    "Account",
    "AuthenticatedSession",
    "MessageAddress",
    "Message",
]
