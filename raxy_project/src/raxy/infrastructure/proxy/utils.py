# -*- coding: utf-8 -*-
"""
Utilitários genéricos para o módulo de proxy.

Contém funções auxiliares para:
- Encodificação/decodificação base64
- Validação de IPs públicos
- Conversão de tipos segura
- Formatação de timestamps
"""

from __future__ import annotations

import base64
import ipaddress
import re
from datetime import datetime, timezone
from typing import Any, Optional


def b64decode_padded(value: str) -> bytes:
    """
    Decodifica base64 tolerando strings sem padding.
    
    Args:
        value: String base64 para decodificar
        
    Returns:
        Bytes decodificados
        
    Example:
        >>> b64decode_padded("SGVsbG8")  # Sem padding
        b'Hello'
    """
    value = value.strip()
    missing = (-len(value)) % 4
    if missing:
        value += "=" * missing
    return base64.urlsafe_b64decode(value)


def sanitize_tag(tag: Optional[str], fallback: str) -> str:
    """
    Normaliza tags para uso seguro em arquivos ou logs.
    
    Remove caracteres especiais e limita o tamanho.
    
    Args:
        tag: Tag original (pode ser None)
        fallback: Valor padrão se tag for inválida
        
    Returns:
        Tag sanitizada
        
    Example:
        >>> sanitize_tag("Servidor @Brasil! (1)", "default")
        'Servidor__Brasil___1_'
    """
    if not tag:
        return fallback
    tag = re.sub(r"[^\w\-\.]+", "_", tag)
    return tag[:48] or fallback


def decode_bytes(data: bytes, *, encoding_hint: Optional[str] = None) -> str:
    """
    Converte bytes em texto testando codificações comuns.
    
    Tenta múltiplas codificações em ordem de preferência.
    
    Args:
        data: Bytes para decodificar
        encoding_hint: Codificação preferencial para tentar primeiro
        
    Returns:
        Texto decodificado
    """
    if not isinstance(data, (bytes, bytearray)):
        return str(data)
    
    encodings: list[str] = []
    if encoding_hint:
        encodings.append(encoding_hint)
    encodings.extend(["utf-8", "utf-8-sig", "latin-1"])
    
    tried: set[str] = set()
    for enc in encodings:
        if not enc or enc in tried:
            continue
        tried.add(enc)
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    
    return data.decode("utf-8", errors="replace")


def safe_int(value: Any) -> Optional[int]:
    """
    Converte valores em int retornando None em caso de falha.
    
    Args:
        value: Valor para converter
        
    Returns:
        Inteiro convertido ou None
        
    Example:
        >>> safe_int("123")
        123
        >>> safe_int("abc")
        None
    """
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> Optional[float]:
    """
    Converte valores em float retornando None em caso de falha.
    
    Args:
        value: Valor para converter
        
    Returns:
        Float convertido ou None
        
    Example:
        >>> safe_float("3.14")
        3.14
        >>> safe_float("invalid")
        None
    """
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def is_public_ip(ip: str) -> bool:
    """
    Verifica se o IP é público e roteável pela Internet.
    
    Exclui IPs privados, loopback, reservados, multicast e link-local.
    
    Args:
        ip: Endereço IP como string
        
    Returns:
        True se o IP for público
        
    Example:
        >>> is_public_ip("8.8.8.8")
        True
        >>> is_public_ip("192.168.1.1")
        False
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_link_local
    )


def format_timestamp(ts: float) -> str:
    """
    Formata timestamp Unix para ISO 8601 UTC.
    
    Args:
        ts: Timestamp Unix (segundos desde epoch)
        
    Returns:
        String no formato ISO 8601 com sufixo Z
        
    Example:
        >>> format_timestamp(0)
        '1970-01-01T00:00:00Z'
    """
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    iso = dt.replace(microsecond=0).isoformat()
    return iso.replace("+00:00", "Z")


def format_destination(host: Optional[str], port: Optional[int]) -> str:
    """
    Monta representação amigável para host:porta.
    
    Args:
        host: Nome do host ou IP
        port: Número da porta
        
    Returns:
        String no formato "host:port" ou "-" se inválido
        
    Example:
        >>> format_destination("example.com", 443)
        'example.com:443'
        >>> format_destination(None, 443)
        '-'
    """
    if not host or host == "-":
        return "-"
    if port is None:
        return host
    return f"{host}:{port}"


__all__ = [
    "b64decode_padded",
    "sanitize_tag",
    "decode_bytes",
    "safe_int",
    "safe_float",
    "is_public_ip",
    "format_timestamp",
    "format_destination",
]
