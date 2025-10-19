"""
Sistema de configuração centralizado do Raxy.

Fornece gerenciamento unificado de todas as configurações da aplicação,
com suporte a variáveis de ambiente, arquivos de configuração e valores padrão.
"""

from .base import BaseConfig, ConfigField
from .app_config import AppConfig
from .executor_config import ExecutorConfig
from .proxy_config import ProxyConfig
from .api_config import APIConfig
from .loader import ConfigLoader

# Instância global de configuração
_config_instance = None


def get_config() -> AppConfig:
    """
    Obtém a configuração global da aplicação.
    
    Returns:
        AppConfig: Configuração global
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader.load()
    return _config_instance


def reload_config() -> AppConfig:
    """
    Recarrega a configuração da aplicação.
    
    Returns:
        AppConfig: Nova configuração carregada
    """
    global _config_instance
    _config_instance = ConfigLoader.load()
    return _config_instance


__all__ = [
    "BaseConfig",
    "ConfigField",
    "AppConfig",
    "ExecutorConfig",
    "ProxyConfig",
    "APIConfig",
    "ConfigLoader",
    "get_config",
    "reload_config",
]
