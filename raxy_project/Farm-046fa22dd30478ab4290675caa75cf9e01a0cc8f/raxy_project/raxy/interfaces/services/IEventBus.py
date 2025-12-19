"""Interface para Event Bus - comunicação assíncrona entre serviços."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict


class IEventBus(ABC):
    """
    Interface para Event Bus - comunicação assíncrona entre serviços.
    
    Permite pub/sub de eventos de domínio entre microserviços desacoplados.
    """
    
    @abstractmethod
    def publish(self, event_name: str, data: Dict[str, Any]) -> None:
        """
        Publica um evento no bus.
        
        Args:
            event_name: Nome do evento (ex: "account.logged_in")
            data: Dados do evento (deve ser serializável em JSON)
        """
        pass
    
    @abstractmethod
    def subscribe(
        self, 
        event_name: str, 
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Inscreve um handler para um evento.
        
        Args:
            event_name: Nome do evento
            handler: Função que processa o evento
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, event_name: str, handler: Callable | None = None) -> None:
        """
        Remove inscrição de um evento.
        
        Args:
            event_name: Nome do evento
            handler: Handler específico (None = remove todos)
        """
        pass
    
    @abstractmethod
    def start(self) -> None:
        """Inicia o event bus (conexões, listeners, etc)."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Para o event bus e limpa recursos."""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Verifica se o bus está rodando."""
        pass
