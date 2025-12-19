"""
Módulo de Configuração do Raxy.

Este pacote centraliza toda a lógica de configuração do sistema.
Use `get_config()` para obter a instância global da configuração.
"""

from typing import Optional

from raxy.config.models import (
    AppConfig, 
    ExecutorConfig, 
    ProxyConfig, 
    APIConfig,
    LoggerConfig,
    SessionConfig
)
from raxy.config.loader import ConfigLoader, ConfigLoaderException
from raxy.config.constants import VALID_ACTIONS, DEFAULT_SELECTORS

# Singleton global
_CONFIG_INSTANCE: Optional[AppConfig] = None


def get_config(reload: bool = False, config_path: str = None) -> AppConfig:
    """
    Obtém a instância global de configuração via Singleton.
    
    Args:
        reload: Se True, recarrega do disco.
        config_path: Caminho opcional para arquivo de config.
    
    Returns:
        AppConfig: Instância da configuração atual.
    """
    global _CONFIG_INSTANCE
    
    if _CONFIG_INSTANCE is None or reload:
        _CONFIG_INSTANCE = ConfigLoader.load(config_path)
        
    return _CONFIG_INSTANCE


__all__ = [
    "get_config",
    "AppConfig",
    "ExecutorConfig",
    "ProxyConfig",
    "APIConfig",
    "LoggerConfig",
    "SessionConfig",
    "ConfigLoaderException",
    "VALID_ACTIONS",
    "DEFAULT_SELECTORS"
]
