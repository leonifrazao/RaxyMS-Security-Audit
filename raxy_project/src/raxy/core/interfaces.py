"""
Interfaces do Núcleo (Core Interfaces).

Define os contratos (Ports) que os Adapters devem implementar.
Segue o princípio de Inversão de Dependência (DIP).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Protocol, Any, Sequence

from raxy.core.domain.accounts import Conta


class AccountRepository(ABC):
    """Interface para persistência de contas."""
    
    @abstractmethod
    def listar(self) -> Sequence[Conta]:
        """Lista todas as contas disponíveis."""
        ...

    @abstractmethod
    def atualizar_pontos(self, email: str, pontos: int) -> bool:
        """Atualiza a pontuação de uma conta."""
        ...


class SessionStateRepository(ABC):
    """
    Interface para persistência de estado da sessão (Cookies, UA).
    Evita acoplamento direto com Redis ou Arquivo.
    """
    
    @abstractmethod
    def save_state(self, account_id: str, key: str, value: Any, ttl: int = 3600) -> bool:
        """Salva um valor de estado."""
        ...
        
    @abstractmethod
    def get_state(self, account_id: str, key: str, default: Any = None) -> Any:
        """Recupera um valor de estado."""
        ...

    @abstractmethod
    def clear_state(self, account_id: str) -> None:
        """Limpa todo o estado da conta."""
        ...


class BrowserDriverProtocol(Protocol):
    """Protocolo que define as capacidades mínimas do driver de navegador."""
    
    def google_get(self, url: str) -> None: ...
    def get_current_url(self) -> str: ...
    def click(self, selector: str, wait: Optional[int] = None) -> None: ...
    def type(self, selector: str, text: str, wait: Optional[int] = None) -> None: ...
    def get_cookies(self) -> Dict[str, str]: ...
    def quit(self) -> None: ...


class NotificationService(ABC):
    """Interface para notificações (Log, Email, Webhook)."""
    
    @abstractmethod
    def notify(self, message: str, level: str = "INFO") -> None:
        ...
