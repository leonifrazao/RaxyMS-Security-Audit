"""Event Handlers - Registry e handlers padrão para eventos."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from raxy.interfaces.services import IEventBus, ILoggingService


class EventHandlerRegistry:
    """
    Registry de handlers de eventos.
    
    Facilita o registro e execução de handlers para eventos específicos.
    
    Exemplo:
        >>> registry = EventHandlerRegistry()
        >>> 
        >>> @registry.handler("account.logged_in")
        >>> def on_login(data: dict):
        ...     print(f"User {data['email']} logged in!")
        >>> 
        >>> registry.register_all(event_bus)
    """
    
    def __init__(self, logger: Optional[ILoggingService] = None):
        """
        Inicializa o registry.
        
        Args:
            logger: Logger customizado
        """
        if logger:
            self._logger = logger
        else:
            from raxy.core.logging import get_logger
            self._logger = get_logger()
        
        self._handlers: Dict[str, List[Callable]] = {}
    
    def handler(self, event_name: str):
        """
        Decorator para registrar um handler.
        
        Args:
            event_name: Nome do evento
        
        Exemplo:
            >>> @registry.handler("account.logged_in")
            >>> def on_login(data: dict):
            ...     print(f"Login: {data['email']}")
        """
        def decorator(func: Callable[[Dict[str, Any]], None]):
            self.add_handler(event_name, func)
            return func
        return decorator
    
    def add_handler(
        self,
        event_name: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Adiciona um handler manualmente.
        
        Args:
            event_name: Nome do evento
            handler: Função handler
        """
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        
        self._handlers[event_name].append(handler)
        self._logger.debug(f"Handler adicionado: {event_name} -> {handler.__name__}")
    
    def remove_handler(
        self,
        event_name: str,
        handler: Optional[Callable] = None
    ) -> None:
        """
        Remove um handler.
        
        Args:
            event_name: Nome do evento
            handler: Handler específico (None = remove todos)
        """
        if event_name not in self._handlers:
            return
        
        if handler is None:
            del self._handlers[event_name]
            self._logger.debug(f"Todos os handlers removidos: {event_name}")
        elif handler in self._handlers[event_name]:
            self._handlers[event_name].remove(handler)
            self._logger.debug(f"Handler removido: {event_name} -> {handler.__name__}")
    
    def get_handlers(self, event_name: str) -> List[Callable]:
        """Retorna handlers de um evento."""
        return self._handlers.get(event_name, [])
    
    def register_all(self, event_bus: IEventBus) -> None:
        """
        Registra todos os handlers no event bus.
        
        Args:
            event_bus: Event bus onde registrar
        """
        for event_name, handlers in self._handlers.items():
            for handler in handlers:
                event_bus.subscribe(event_name, handler)
        
        self._logger.info(f"Registrados {len(self._handlers)} eventos no Event Bus")
    
    def unregister_all(self, event_bus: IEventBus) -> None:
        """
        Remove todos os handlers do event bus.
        
        Args:
            event_bus: Event bus onde desregistrar
        """
        for event_name in self._handlers.keys():
            event_bus.unsubscribe(event_name)
        
        self._logger.info("Handlers desregistrados do Event Bus")


# ==================== Handlers Padrão ====================

def create_logging_handler(logger: Optional[ILoggingService] = None):
    """
    Cria um handler que apenas loga eventos.
    
    Útil para debugging e monitoramento.
    
    Args:
        logger: Logger customizado
    
    Returns:
        Handler function
    """
    if logger:
        _logger = logger
    else:
        from raxy.core.logging import get_logger
        _logger = get_logger()
    
    def log_event(data: Dict[str, Any]) -> None:
        event_type = data.get("event_type", "unknown")
        _logger.info(f"Evento recebido: {event_type}")
    
    return log_event


def create_metrics_handler(metrics_collector=None):
    """
    Cria um handler que coleta métricas de eventos.
    
    Args:
        metrics_collector: Coletor de métricas (ex: Prometheus)
    
    Returns:
        Handler function
    """
    def collect_metrics(data: Dict[str, Any]) -> None:
        if metrics_collector:
            event_type = data.get("event_type", "unknown")
            # metrics_collector.increment(f"events.{event_type}")
            pass
    
    return collect_metrics


def create_persistence_handler(repository=None):
    """
    Cria um handler que persiste eventos.
    
    Args:
        repository: Repositório para salvar eventos
    
    Returns:
        Handler function
    """
    def persist_event(data: Dict[str, Any]) -> None:
        if repository:
            # repository.save_event(data)
            pass
    
    return persist_event
