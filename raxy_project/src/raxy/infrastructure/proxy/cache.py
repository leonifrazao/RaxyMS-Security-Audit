# -*- coding: utf-8 -*-
"""
Gerenciador de cache para resultados de testes de proxy.

Persiste os resultados de testes para acelerar execuções futuras,
evitando testar novamente proxies que já foram validadas.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from raxy.infrastructure.proxy.utils import format_timestamp, safe_float


class ProxyCacheManager:
    """
    Gerencia o cache de proxies testadas.
    
    Salva e carrega resultados de testes em formato JSON para
    evitar re-testar proxies conhecidas.
    
    Attributes:
        cache_path: Caminho para o arquivo de cache
        version: Versão do formato do cache
        
    Example:
        >>> cache = ProxyCacheManager(Path("proxy_cache.json"))
        >>> cache.load()
        >>> entry = cache.get("vmess://...")
        >>> cache.save(entries_list)
    """
    
    CACHE_VERSION: int = 1
    DEFAULT_FILENAME: str = "proxy_cache.json"
    
    def __init__(
        self, 
        cache_path: Optional[Path] = None,
        *,
        enabled: bool = True
    ) -> None:
        """
        Inicializa o gerenciador de cache.
        
        Args:
            cache_path: Caminho para arquivo de cache. Se None, usa default.
            enabled: Se o cache está habilitado
        """
        self.enabled = enabled
        self.cache_path = cache_path or Path(__file__).with_name(self.DEFAULT_FILENAME)
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
    
    @property
    def is_available(self) -> bool:
        """Indica se há dados de cache disponíveis."""
        return self.enabled and bool(self._entries)
    
    def load(self) -> bool:
        """
        Carrega resultados persistidos do arquivo de cache.
        
        Returns:
            True se carregou com sucesso, False caso contrário
        """
        if not self.enabled:
            return False
        
        self._entries = {}
        self._loaded = False
        
        try:
            raw_cache = self.cache_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False
        except OSError:
            return False

        try:
            data = json.loads(raw_cache)
        except json.JSONDecodeError:
            return False

        if not isinstance(data, dict):
            return False
        
        entries = data.get("entries")
        if not isinstance(entries, list):
            return False

        cache_map: Dict[str, Dict[str, Any]] = {}
        for item in entries:
            if not isinstance(item, dict):
                continue
            uri = item.get("uri")
            if not isinstance(uri, str) or not uri.strip():
                continue
            cache_map[uri] = item

        self._entries = cache_map
        self._loaded = bool(cache_map)
        return self._loaded
    
    def get(self, uri: str) -> Optional[Dict[str, Any]]:
        """
        Recupera dados de cache para uma URI.
        
        Args:
            uri: URI do proxy
            
        Returns:
            Dict com dados em cache ou None se não existir
        """
        if not self.enabled:
            return None
        return self._entries.get(uri)
    
    def save(self, entries: List[Dict[str, Any]]) -> bool:
        """
        Persiste a última bateria de testes no cache.
        
        Args:
            entries: Lista de dicionários com resultados de teste
            
        Returns:
            True se salvou com sucesso
        """
        if not self.enabled:
            return False
        
        # Garante que o diretório existe
        cache_dir = self.cache_path.parent
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        payload_entries = [
            prepared 
            for entry in entries 
            if (prepared := self._prepare_entry(entry))
        ]

        payload = {
            "version": self.CACHE_VERSION,
            "generated_at": format_timestamp(time.time()),
            "entries": payload_entries,
        }

        try:
            self.cache_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return False
        
        # Atualiza cache em memória
        self._entries = {item["uri"]: item for item in payload_entries}
        return True
    
    def _prepare_entry(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Prepara uma entrada para persistência no cache.
        
        Args:
            entry: Dicionário com dados da proxy
            
        Returns:
            Dicionário pronto para serialização ou None se inválido
        """
        if not isinstance(entry, dict):
            return None
        
        uri = entry.get("uri")
        if not isinstance(uri, str) or not uri.strip():
            return None

        tested_ts = safe_float(entry.get("tested_at_ts"))
        if tested_ts is None:
            tested_ts = time.time()

        tested_at = entry.get("tested_at")
        if not isinstance(tested_at, str) or not tested_at.strip():
            tested_at = format_timestamp(tested_ts)

        return {
            "uri": uri,
            "tag": entry.get("tag"),
            "status": entry.get("status"),
            "host": entry.get("host"),
            "port": entry.get("port"),
            "ip": entry.get("ip"),
            "country": entry.get("country"),
            "country_code": entry.get("country_code"),
            "country_name": entry.get("country_name"),
            "proxy_ip": entry.get("proxy_ip"),
            "proxy_country": entry.get("proxy_country"),
            "proxy_country_code": entry.get("proxy_country_code"),
            "ping": entry.get("ping"),
            "error": entry.get("error"),
            "tested_at": tested_at,
            "tested_at_ts": tested_ts,
        }
    
    def apply_to_entry(
        self, 
        entry: Dict[str, Any], 
        cached: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Mescla dados do cache ao registro corrente da proxy.
        
        Args:
            entry: Entrada atual (vazia ou parcial)
            cached: Dados do cache
            
        Returns:
            Entrada atualizada com dados do cache
        """
        if not cached:
            return entry
        
        merged = dict(entry)

        text_fields = (
            "status", "host", "ip", "country", "country_code", 
            "country_name", "proxy_ip", "proxy_country",
            "proxy_country_code", "error", "tested_at",
        )

        for key in text_fields:
            if key not in cached:
                continue
            value = cached.get(key)
            if isinstance(value, str):
                normalized = value.strip()
                if not normalized and key not in {"status", "error"}:
                    continue
                merged[key] = normalized or merged.get(key)
            elif value is not None:
                merged[key] = value

        # Campos numéricos
        port_value = cached.get("port")
        if port_value is not None:
            from raxy.infrastructure.proxy.utils import safe_int
            parsed_port = safe_int(port_value)
            if parsed_port is not None:
                merged["port"] = parsed_port

        ping_value = cached.get("ping", cached.get("ping_ms"))
        if ping_value is not None:
            parsed_ping = safe_float(ping_value)
            if parsed_ping is not None:
                merged["ping"] = parsed_ping

        tested_at_ts = safe_float(cached.get("tested_at_ts"))
        if tested_at_ts is not None:
            merged["tested_at_ts"] = tested_at_ts

        merged["cached"] = True
        return merged
    
    def clear(self) -> bool:
        """
        Remove o arquivo de cache.
        
        Returns:
            True se removeu com sucesso
        """
        try:
            if self.cache_path.exists():
                self.cache_path.unlink()
            self._entries = {}
            return True
        except OSError:
            return False


__all__ = ["ProxyCacheManager"]
