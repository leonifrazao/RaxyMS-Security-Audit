"""
Entidades do MailTM.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Domain:
    """Representa um domínio de e-mail disponível."""
    id: str
    domain: str
    is_active: bool = True
    is_private: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class MailAccount:
    """Representa uma conta de e-mail do MailTM."""
    id: str
    address: str
    is_disabled: bool
    is_deleted: bool
    created_at: str
    updated_at: str


@dataclass
class AuthenticatedSession:
    """Agrupa os dados de uma sessão autenticada (conta + token)."""
    account: MailAccount
    token: str


@dataclass
class MessageAddress:
    """Representa um endereço de e-mail (remetente/destinatário) em uma mensagem."""
    address: str
    name: str


@dataclass
class Message:
    """Representa uma mensagem de e-mail."""
    id: str
    account_id: str
    msgid: str
    from_address: MessageAddress = field(metadata={'name': 'from'})
    to: List[MessageAddress] = field(default_factory=list)
    subject: str = ""
    intro: str = ""
    seen: bool = False
    is_deleted: bool = False
    has_attachments: bool = False
    size: int = 0
    download_url: str = ""
    created_at: str = ""
    updated_at: str = ""
