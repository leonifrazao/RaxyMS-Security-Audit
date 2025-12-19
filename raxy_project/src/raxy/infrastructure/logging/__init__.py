"""
Sistema de logging modular e eficiente para o Raxy.

Este módulo fornece um sistema de logging completo e extensível,
dividido em componentes especializados seguindo o princípio SOLID.
"""

from raxy.config import LoggerConfig
from .logger import RaxyLogger
from .context import LogContext
from .formatters import LogFormatter
from .handlers import LogHandler
from .debug_decorator import debug_log, debug

# Singleton do logger principal
_logger_instance = None


def get_logger() -> RaxyLogger:
    """Retorna a instância singleton do logger."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = RaxyLogger()
    return _logger_instance


# Exporta a instância global
log = get_logger()

__all__ = [
    "LoggerConfig",
    "RaxyLogger", 
    "LogContext",
    "LogFormatter",
    "LogHandler",
    "get_logger",
    "log",
    "debug_log",
    "debug",
]
