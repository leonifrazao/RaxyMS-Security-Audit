"""
Compatibility Shim for Configuration.

Este arquivo existe apenas para manter compatibilidade com módulos não refatorados (ex: Proxy).
Toda a lógica real foi movida para `raxy.config`.
"""

from raxy.config import (
    get_config, 
    AppConfig, 
    ExecutorConfig, 
    ProxyConfig, 
    APIConfig,
    LoggerConfig,
    SessionConfig,
    VALID_ACTIONS,
    DEFAULT_SELECTORS
)

# Re-export de classes que podem ser importadas diretamente
__all__ = [
    "get_config",
    "AppConfig",
    "ExecutorConfig",
    "ProxyConfig",
    "APIConfig",
    "LoggerConfig",
    "SessionConfig",
    "VALID_ACTIONS",
    "DEFAULT_SELECTORS"
]
