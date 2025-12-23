# mailtm_models.py
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Domain:
    """Representa um domínio de e-mail disponível."""
    id: str
    domain: str
    is_active: bool
    is_private: bool
    created_at: str
    updated_at: str

@dataclass
class Account:
    """Representa uma conta de e-mail."""
    id: str
    address: str
    is_disabled: bool
    is_deleted: bool
    created_at: str
    updated_at: str

@dataclass
class AuthenticatedSession:
    """Agrupa os dados de uma sessão autenticada (conta + token)."""
    account: Account
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
    to: List[MessageAddress]
    subject: str
    intro: str
    seen: bool
    is_deleted: bool
    has_attachments: bool
    size: int
    download_url: str
    created_at: str
    updated_at: str