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


# ==================== Handlers de Domínio ====================

def create_rewards_handler(logger: Optional[ILoggingService] = None):
    """
    Cria handlers para eventos de rewards.
    
    Args:
        logger: Logger customizado
    
    Returns:
        Dict com handlers de rewards
    """
    if logger:
        _logger = logger
    else:
        from raxy.core.logging import get_logger
        _logger = get_logger()
    
    def on_points_fetched(data: Dict[str, Any]) -> None:
        account_id = data.get("account_id", "unknown")
        points = data.get("points", 0)
        _logger.debug(f"Pontos obtidos: {points} para {account_id}")
    
    def on_rewards_collected(data: Dict[str, Any]) -> None:
        account_id = data.get("account_id", "unknown")
        completed = data.get("tasks_completed", 0)
        total = data.get("total_tasks", 0)
        _logger.info(f"Recompensas coletadas: {completed}/{total} para {account_id}")
    
    def on_task_completed(data: Dict[str, Any]) -> None:
        task_id = data.get("task_id", "unknown")
        points = data.get("points_earned", 0)
        _logger.debug(f"Tarefa {task_id} completada: +{points} pontos")
    
    return {
        "rewards.points.fetched": on_points_fetched,
        "rewards.collected": on_rewards_collected,
        "task.completed": on_task_completed,
    }


def create_session_handler(logger: Optional[ILoggingService] = None):
    """
    Cria handlers para eventos de sessão.
    
    Args:
        logger: Logger customizado
    
    Returns:
        Dict com handlers de sessão
    """
    if logger:
        _logger = logger
    else:
        from raxy.core.logging import get_logger
        _logger = get_logger()
    
    def on_session_started(data: Dict[str, Any]) -> None:
        account_id = data.get("account_id", "unknown")
        proxy_id = data.get("proxy_id", "none")
        _logger.debug(f"Sessão iniciada: {account_id} via proxy {proxy_id}")
    
    def on_session_ended(data: Dict[str, Any]) -> None:
        account_id = data.get("account_id", "unknown")
        duration = data.get("duration_seconds", 0)
        _logger.debug(f"Sessão encerrada: {account_id} ({duration:.1f}s)")
    
    def on_session_error(data: Dict[str, Any]) -> None:
        account_id = data.get("account_id", "unknown")
        error_type = data.get("error_type", "unknown")
        is_recoverable = data.get("is_recoverable", False)
        level = "aviso" if is_recoverable else "erro"
        _logger.debug(f"[{level}] Erro na sessão {account_id}: {error_type}")
    
    return {
        "session.started": on_session_started,
        "session.ended": on_session_ended,
        "session.error": on_session_error,
    }


def create_account_handler(logger: Optional[ILoggingService] = None):
    """
    Cria handlers para eventos de contas.
    
    Args:
        logger: Logger customizado
    
    Returns:
        Dict com handlers de contas
    """
    if logger:
        _logger = logger
    else:
        from raxy.core.logging import get_logger
        _logger = get_logger()
    
    def on_logged_in(data: Dict[str, Any]) -> None:
        email = data.get("email", "unknown")
        _logger.debug(f"Login: {email}")
    
    def on_logged_out(data: Dict[str, Any]) -> None:
        email = data.get("email", "unknown")
        _logger.debug(f"Logout: {email}")
    
    return {
        "account.logged_in": on_logged_in,
        "account.logged_out": on_logged_out,
    }


def create_executor_handler(logger: Optional[ILoggingService] = None):
    """
    Cria handlers para eventos de executor.
    
    Args:
        logger: Logger customizado
    
    Returns:
        Dict com handlers de executor
    """
    if logger:
        _logger = logger
    else:
        from raxy.core.logging import get_logger
        _logger = get_logger()
    
    def on_batch_completed(data: Dict[str, Any]) -> None:
        total = data.get("total_accounts", 0)
        success = data.get("success_count", 0)
        points = data.get("total_points", 0)
        _logger.info(f"Execução em lote concluída: {success}/{total} contas, {points} pontos totais")
    
    def on_account_completed(data: Dict[str, Any]) -> None:
        account_id = data.get("account_id", "unknown")
        points = data.get("points_earned", 0)
        _logger.debug(f"Conta {account_id} processada: +{points} pontos")
    
    return {
        "executor.batch_completed": on_batch_completed,
        "executor.account_completed": on_account_completed,
    }


def create_flyout_handler(logger: Optional[ILoggingService] = None):
    """
    Cria handlers para eventos de flyout.
    
    Args:
        logger: Logger customizado
    
    Returns:
        Dict com handlers de flyout
    """
    if logger:
        _logger = logger
    else:
        from raxy.core.logging import get_logger
        _logger = get_logger()
    
    def on_flyout_completed(data: Dict[str, Any]) -> None:
        account_id = data.get("account_id", "unknown")
        _logger.debug(f"Flyout completado: {account_id}")
    
    def on_bug_detected(data: Dict[str, Any]) -> None:
        account_id = data.get("account_id", "unknown")
        bug_type = data.get("bug_type", "unknown")
        _logger.aviso(f"Bug detectado em {account_id}: {bug_type}")
    
    def on_flyout_error(data: Dict[str, Any]) -> None:
        account_id = data.get("account_id", "unknown")
        error_type = data.get("error_type", "unknown")
        _logger.erro(f"Erro no flyout {account_id}: {error_type}")
    
    return {
        "flyout.completed": on_flyout_completed,
        "flyout.bug_detected": on_bug_detected,
        "flyout.error": on_flyout_error,
    }


def create_bing_handler(logger: Optional[ILoggingService] = None):
    """
    Cria handlers para eventos de Bing.
    
    Args:
        logger: Logger customizado
    
    Returns:
        Dict com handlers de Bing
    """
    if logger:
        _logger = logger
    else:
        from raxy.core.logging import get_logger
        _logger = get_logger()
    
    def on_suggestions_fetched(data: Dict[str, Any]) -> None:
        keyword = data.get("keyword", "unknown")
        count = data.get("suggestions_count", 0)
        _logger.debug(f"Sugestões obtidas para '{keyword}': {count}")
    
    return {
        "bing.suggestions.fetched": on_suggestions_fetched,
    }


def create_mail_handler(logger: Optional[ILoggingService] = None):
    """
    Cria handlers para eventos de email.
    
    Args:
        logger: Logger customizado
    
    Returns:
        Dict com handlers de email
    """
    if logger:
        _logger = logger
    else:
        from raxy.core.logging import get_logger
        _logger = get_logger()
    
    def on_account_created(data: Dict[str, Any]) -> None:
        address = data.get("address", "unknown")
        _logger.debug(f"Conta de email criada: {address}")
    
    def on_message_received(data: Dict[str, Any]) -> None:
        subject = data.get("subject", "unknown")
        _logger.debug(f"Mensagem recebida: {subject}")
    
    return {
        "mail.account.created": on_account_created,
        "mail.message.received": on_message_received,
    }


def create_profile_handler(logger: Optional[ILoggingService] = None):
    """
    Cria handlers para eventos de perfil.
    
    Args:
        logger: Logger customizado
    
    Returns:
        Dict com handlers de perfil
    """
    if logger:
        _logger = logger
    else:
        from raxy.core.logging import get_logger
        _logger = get_logger()
    
    def on_profile_created(data: Dict[str, Any]) -> None:
        profile_id = data.get("profile_id", "unknown")
        account_id = data.get("account_id", "unknown")
        _logger.debug(f"Perfil criado: {profile_id} para {account_id}")
    
    def on_ua_regenerated(data: Dict[str, Any]) -> None:
        profile_id = data.get("profile_id", "unknown")
        _logger.debug(f"User-Agent regenerado para perfil: {profile_id}")
    
    return {
        "profile.created": on_profile_created,
        "profile.ua_regenerated": on_ua_regenerated,
    }


def create_request_handler(logger: Optional[ILoggingService] = None):
    """
    Cria handlers para eventos de requisição.
    
    Args:
        logger: Logger customizado
    
    Returns:
        Dict com handlers de requisição
    """
    if logger:
        _logger = logger
    else:
        from raxy.core.logging import get_logger
        _logger = get_logger()
    
    def on_request_completed(data: Dict[str, Any]) -> None:
        method = data.get("method", "unknown")
        url = data.get("url", "unknown")
        status = data.get("status_code", 0)
        success = data.get("success", False)
        
        if success:
            _logger.debug(f"Request {method} {url}: {status}")
        else:
            _logger.aviso(f"Request {method} {url} falhou: {status}")
    
    return {
        "request.completed": on_request_completed,
    }


def register_default_handlers(event_bus: IEventBus, logger: Optional[ILoggingService] = None) -> None:
    """
    Registra todos os handlers padrão no event bus.
    
    Args:
        event_bus: Event bus onde registrar
        logger: Logger customizado
    """
    # Rewards handlers
    rewards_handlers = create_rewards_handler(logger)
    for event_name, handler in rewards_handlers.items():
        event_bus.subscribe(event_name, handler)
    
    # Session handlers
    session_handlers = create_session_handler(logger)
    for event_name, handler in session_handlers.items():
        event_bus.subscribe(event_name, handler)
    
    # Account handlers
    account_handlers = create_account_handler(logger)
    for event_name, handler in account_handlers.items():
        event_bus.subscribe(event_name, handler)
    
    # Executor handlers
    executor_handlers = create_executor_handler(logger)
    for event_name, handler in executor_handlers.items():
        event_bus.subscribe(event_name, handler)
    
    # Flyout handlers
    flyout_handlers = create_flyout_handler(logger)
    for event_name, handler in flyout_handlers.items():
        event_bus.subscribe(event_name, handler)
    
    # Bing handlers
    bing_handlers = create_bing_handler(logger)
    for event_name, handler in bing_handlers.items():
        event_bus.subscribe(event_name, handler)
    
    # Mail handlers
    mail_handlers = create_mail_handler(logger)
    for event_name, handler in mail_handlers.items():
        event_bus.subscribe(event_name, handler)
    
    # Profile handlers
    profile_handlers = create_profile_handler(logger)
    for event_name, handler in profile_handlers.items():
        event_bus.subscribe(event_name, handler)
    
    # Request handlers
    request_handlers = create_request_handler(logger)
    for event_name, handler in request_handlers.items():
        event_bus.subscribe(event_name, handler)
