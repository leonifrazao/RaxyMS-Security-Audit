# -*- coding: utf-8 -*-
"""
Módulo de gerenciamento de proxies V2Ray/Xray.

Este pacote fornece funcionalidades para:
- Parsing de URIs de proxy (ss, vmess, vless, trojan)
- Testes de conectividade real via pontes HTTP
- Cache de resultados de testes
- Gerenciamento de pontes HTTP locais com Xray

Uso básico:
    >>> from raxy.infrastructure.proxy import ProxyManager
    >>> manager = ProxyManager(sources=["proxies.txt"])
    >>> manager.test(threads=10, country="US")
    >>> manager.start(amounts=5)
"""

from raxy.infrastructure.proxy.manager import ProxyManager
from raxy.infrastructure.proxy.models import Outbound, BridgeRuntime
from raxy.infrastructure.proxy.parser import ProxyURIParser, parse_proxy_uri
from raxy.infrastructure.proxy.cache import ProxyCacheManager
from raxy.infrastructure.proxy.display import ProxyDisplayManager
from raxy.infrastructure.proxy.bridge import XrayBridgeManager

__all__ = [
    "ProxyManager",
    "Outbound",
    "BridgeRuntime",
    "ProxyURIParser",
    "parse_proxy_uri",
    "ProxyCacheManager",
    "ProxyDisplayManager", 
    "XrayBridgeManager",
]
