"""
Pacote de Modelos (Entidades) do Domínio.

Centraliza todas as estruturas de dados do sistema.
"""

from .account import Conta
from .proxy import Proxy
from .session import SessionState
from .execution import ContaResult, ExecucaoResult
from .mailtm import MailAccount, Domain, Message, AuthenticatedSession

__all__ = [
    "Conta",
    "Proxy",
    "SessionState",
    "ContaResult",
    "ExecucaoResult",
    "MailAccount",
    "Domain",
    "Message",
    "AuthenticatedSession",
]
