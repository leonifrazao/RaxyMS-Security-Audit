"""
Infrastructure Module

Contains:
- config: Configuration management
- logging: Logging system  
- http: HTTP clients (Botasaurus)
- proxy: Proxy management (V2Ray/Xray)
- utils: Shared utilities
"""

from raxy.infrastructure.logging import get_logger
from raxy.infrastructure.config.config import get_config
from raxy.infrastructure.manager import ProxyManager

__all__ = [
    "get_logger",
    "get_config",
    "ProxyManager",
]

