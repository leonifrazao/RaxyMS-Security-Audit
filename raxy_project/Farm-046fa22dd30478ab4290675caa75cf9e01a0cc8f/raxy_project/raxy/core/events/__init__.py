"""
Sistema de eventos para arquitetura Event-Driven.

Este módulo fornece Event Bus (Redis Pub/Sub) e handlers de eventos.
"""

from .redis_bus import RedisEventBus
from .handlers import EventHandlerRegistry
from .event_logging import (
    LogEvent,
    create_log_event,
    LogAggregator,
    LogDestination,
    ConsoleLogDestination,
    FileLogDestination,
    JSONLogDestination,
)


__all__ = [
    "RedisEventBus",
    "EventHandlerRegistry",
    "create_logging_handler",
    "create_metrics_handler",
    "create_persistence_handler",
    "create_rewards_handler",
    "create_session_handler",
    "create_account_handler",
    "create_executor_handler",
    "create_flyout_handler",
    "create_bing_handler",
    "create_mail_handler",
    "create_profile_handler",
    "create_request_handler",
    "register_default_handlers",
    "LogEvent",
    "create_log_event",
    "LogAggregator",
    "LogDestination",
    "ConsoleLogDestination",
    "FileLogDestination",
    "JSONLogDestination",
]
