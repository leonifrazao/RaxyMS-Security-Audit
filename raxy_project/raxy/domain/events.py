"""Domain Events - Eventos de domínio do sistema Raxy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class DomainEvent:
    """Evento base de domínio."""
    
    event_id: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa evento para dicionário."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            **self._get_payload()
        }
    
    def _get_payload(self) -> Dict[str, Any]:
        """Retorna payload específico do evento."""
        return {}


# ==================== Account Events ====================

@dataclass
class AccountLoggedIn(DomainEvent):
    """Evento: conta autenticada com sucesso."""
    
    account_id: str = ""
    email: str = ""
    profile_id: str = ""
    proxy_id: Optional[str] = None
    market: Optional[str] = None
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "email": self.email,
            "profile_id": self.profile_id,
            "proxy_id": self.proxy_id,
            "market": self.market,
        }


@dataclass
class AccountLoggedOut(DomainEvent):
    """Evento: conta desconectada."""
    
    account_id: str = ""
    email: str = ""
    reason: Optional[str] = None
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "email": self.email,
            "reason": self.reason,
        }


@dataclass
class ProfileCreated(DomainEvent):
    """Evento: novo perfil criado."""
    
    profile_id: str = ""
    email: str = ""
    user_agent: str = ""
    temp_email: Optional[str] = None
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "email": self.email,
            "user_agent": self.user_agent,
            "temp_email": self.temp_email,
        }


# ==================== Rewards Events ====================

@dataclass
class RewardsCollected(DomainEvent):
    """Evento: recompensas coletadas."""
    
    account_id: str = ""
    points_before: int = 0
    points_after: int = 0
    points_gained: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "points_before": self.points_before,
            "points_after": self.points_after,
            "points_gained": self.points_gained,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
        }


@dataclass
class TaskCompleted(DomainEvent):
    """Evento: tarefa completada."""
    
    account_id: str = ""
    task_id: str = ""
    task_type: str = ""
    points_earned: int = 0
    duration_seconds: float = 0.0
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "points_earned": self.points_earned,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class TaskFailed(DomainEvent):
    """Evento: tarefa falhou."""
    
    account_id: str = ""
    task_id: str = ""
    task_type: str = ""
    error_message: str = ""
    retry_count: int = 0
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }


# ==================== Proxy Events ====================

@dataclass
class ProxyRotated(DomainEvent):
    """Evento: proxy rotacionada."""
    
    old_proxy_id: Optional[str] = None
    new_proxy_id: str = ""
    old_proxy_url: Optional[str] = None
    new_proxy_url: str = ""
    reason: str = ""
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "old_proxy_id": self.old_proxy_id,
            "new_proxy_id": self.new_proxy_id,
            "old_proxy_url": self.old_proxy_url,
            "new_proxy_url": self.new_proxy_url,
            "reason": self.reason,
        }


@dataclass
class ProxyFailed(DomainEvent):
    """Evento: proxy falhou."""
    
    proxy_id: str = ""
    proxy_url: str = ""
    error_type: str = ""
    error_message: str = ""
    status_code: Optional[int] = None
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "proxy_id": self.proxy_id,
            "proxy_url": self.proxy_url,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "status_code": self.status_code,
        }


# ==================== Session Events ====================

@dataclass
class SessionStarted(DomainEvent):
    """Evento: sessão iniciada."""
    
    session_id: str = ""
    account_id: str = ""
    proxy_id: Optional[str] = None
    user_agent: str = ""
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "proxy_id": self.proxy_id,
            "user_agent": self.user_agent,
        }


@dataclass
class SessionEnded(DomainEvent):
    """Evento: sessão encerrada."""
    
    session_id: str = ""
    account_id: str = ""
    duration_seconds: float = 0.0
    reason: str = ""
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "duration_seconds": self.duration_seconds,
            "reason": self.reason,
        }


@dataclass
class SessionError(DomainEvent):
    """Evento: erro na sessão."""
    
    session_id: str = ""
    account_id: str = ""
    error_type: str = ""
    error_message: str = ""
    is_recoverable: bool = False
    
    def _get_payload(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "is_recoverable": self.is_recoverable,
        }
