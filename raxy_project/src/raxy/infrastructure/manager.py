# -*- coding: utf-8 -*-
"""
Módulo de compatibilidade - Redireciona para a versão refatorada.

NOTA: Este arquivo foi refatorado e modularizado.
O código original de 2120 linhas foi dividido em módulos menores:

- raxy.infrastructure.proxy.manager (ProxyManager principal)
- raxy.infrastructure.proxy.parser (parsing de URIs)
- raxy.infrastructure.proxy.cache (gerenciamento de cache)
- raxy.infrastructure.proxy.bridge (pontes Xray)
- raxy.infrastructure.proxy.display (formatação Rich)
- raxy.infrastructure.proxy.utils (utilitários)
- raxy.infrastructure.proxy.models (dataclasses)

Este arquivo mantém compatibilidade com imports existentes.
"""

from __future__ import annotations

# Re-exporta tudo do novo módulo para manter compatibilidade
from raxy.infrastructure.proxy import ProxyManager
from raxy.infrastructure.proxy.models import Outbound, BridgeRuntime
from raxy.infrastructure.proxy.utils import (
    b64decode_padded,
    sanitize_tag,
    decode_bytes,
    safe_int,
    safe_float,
    is_public_ip,
    format_timestamp,
    format_destination,
)
from raxy.infrastructure.proxy.parser import ProxyURIParser, parse_proxy_uri
from raxy.infrastructure.proxy.cache import ProxyCacheManager
from raxy.infrastructure.proxy.display import ProxyDisplayManager, RICH_AVAILABLE
from raxy.infrastructure.proxy.bridge import XrayBridgeManager

__all__ = [
    # Classe principal
    "ProxyManager",
    # Modelos
    "Outbound",
    "BridgeRuntime",
    # Componentes
    "ProxyURIParser",
    "ProxyCacheManager",
    "ProxyDisplayManager",
    "XrayBridgeManager",
    # Funções utilitárias
    "parse_proxy_uri",
    "b64decode_padded",
    "sanitize_tag",
    "decode_bytes",
    "safe_int",
    "safe_float",
    "is_public_ip",
    "format_timestamp",
    "format_destination",
    # Flags
    "RICH_AVAILABLE",
]