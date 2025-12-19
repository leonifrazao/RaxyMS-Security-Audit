# -*- coding: utf-8 -*-
"""
Modelos de dados para o módulo de proxy.

Define as dataclasses e tipos utilizados pelo ProxyManager.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import Popen
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Outbound:
    """
    Representa um outbound configurado para o Xray/V2Ray.
    
    Attributes:
        tag: Identificador único do outbound
        config: Dicionário com configuração completa do Xray
    """
    tag: str
    config: Dict[str, Any]


@dataclass
class BridgeRuntime:
    """
    Representa uma ponte HTTP ativa e seus recursos associados.
    
    Gerencia o ciclo de vida de um processo Xray que atua como
    ponte HTTP local para um proxy remoto.
    
    Attributes:
        tag: Identificador da ponte (nome da proxy)
        port: Porta local onde a ponte escuta
        scheme: Protocolo do proxy (ss, vmess, vless, trojan)
        uri: URI original do proxy
        process: Processo Xray em execução
        workdir: Diretório temporário com arquivos de config
    """
    tag: str
    port: int
    scheme: str
    uri: str
    process: Optional[Popen[bytes]]
    workdir: Optional[Path]

    @property
    def url(self) -> str:
        """
        URL HTTP local para usar como proxy.
        
        Returns:
            URL no formato http://127.0.0.1:{port}
        """
        return f"http://127.0.0.1:{self.port}"


@dataclass
class ProxyEntry:
    """
    Registro de uma proxy com status de teste.
    
    Representa o estado completo de uma proxy incluindo
    resultados de testes anteriores.
    
    Attributes:
        index: Índice na lista de outbounds
        tag: Nome/identificador da proxy
        uri: URI original
        status: Estado atual (AGUARDANDO, TESTANDO, OK, ERRO, FILTRADO)
        host: Hostname do servidor
        port: Porta do servidor
        ip: IP resolvido do servidor
        country: País de saída (display)
        country_code: Código do país ISO2
        country_name: Nome completo do país
        proxy_ip: IP real de saída (pode diferir do servidor)
        proxy_country: País do IP de saída
        proxy_country_code: Código do país de saída
        ping: Latência em ms
        error: Mensagem de erro (se houver)
        country_match: Se corresponde ao filtro de país
        tested_at: Timestamp ISO do teste
        tested_at_ts: Timestamp Unix do teste
        cached: Se dados vieram do cache
        functional: Se proxy está funcional
        external_ip: IP externo detectado via httpbin
    """
    index: int
    tag: str
    uri: str
    status: str = "AGUARDANDO"
    host: str = "-"
    port: Optional[int] = None
    ip: str = "-"
    country: str = "-"
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    proxy_ip: Optional[str] = None
    proxy_country: Optional[str] = None
    proxy_country_code: Optional[str] = None
    ping: Optional[float] = None
    error: Optional[str] = None
    country_match: Optional[bool] = None
    tested_at: Optional[str] = None
    tested_at_ts: Optional[float] = None
    cached: bool = False
    functional: bool = False
    external_ip: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte para dicionário para compatibilidade com código legado.
        
        Returns:
            Dict com todos os campos
        """
        return {
            "index": self.index,
            "tag": self.tag,
            "uri": self.uri,
            "status": self.status,
            "host": self.host,
            "port": self.port,
            "ip": self.ip,
            "country": self.country,
            "country_code": self.country_code,
            "country_name": self.country_name,
            "proxy_ip": self.proxy_ip,
            "proxy_country": self.proxy_country,
            "proxy_country_code": self.proxy_country_code,
            "ping": self.ping,
            "error": self.error,
            "country_match": self.country_match,
            "tested_at": self.tested_at,
            "tested_at_ts": self.tested_at_ts,
            "cached": self.cached,
            "functional": self.functional,
            "external_ip": self.external_ip,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProxyEntry":
        """
        Cria instância a partir de dicionário.
        
        Args:
            data: Dicionário com campos da entry
            
        Returns:
            Nova instância de ProxyEntry
        """
        return cls(
            index=data.get("index", 0),
            tag=data.get("tag", ""),
            uri=data.get("uri", ""),
            status=data.get("status", "AGUARDANDO"),
            host=data.get("host", "-"),
            port=data.get("port"),
            ip=data.get("ip", "-"),
            country=data.get("country", "-"),
            country_code=data.get("country_code"),
            country_name=data.get("country_name"),
            proxy_ip=data.get("proxy_ip"),
            proxy_country=data.get("proxy_country"),
            proxy_country_code=data.get("proxy_country_code"),
            ping=data.get("ping"),
            error=data.get("error"),
            country_match=data.get("country_match"),
            tested_at=data.get("tested_at"),
            tested_at_ts=data.get("tested_at_ts"),
            cached=data.get("cached", False),
            functional=data.get("functional", False),
            external_ip=data.get("external_ip"),
        )


__all__ = ["Outbound", "BridgeRuntime", "ProxyEntry"]
