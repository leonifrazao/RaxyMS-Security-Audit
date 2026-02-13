# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from raxy.models.proxy import Outbound, ProxyItem, ProxyTestResult

DEFAULT_CACHE_FILENAME: str = "proxy_cache.json"
CACHE_VERSION: int = 1


def safe_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> Optional[float]:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def format_timestamp(ts: float) -> str:
    """Retorna carimbo de data no formato ISO 8601 UTC sem microssegundos."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    iso = dt.replace(microsecond=0).isoformat()
    return iso.replace("+00:00", "Z")


def make_base_entry(index: int, raw_uri: str, outbound: Outbound) -> ProxyItem:
    """Monta o objeto padrão com as informações mínimas de um outbound."""
    return ProxyItem(
        index=index,
        uri=raw_uri,
        tag=outbound.tag,
        outbound=outbound,
    )


def _parse_cached_result(data: Dict[str, Any]) -> ProxyTestResult:
    """Converte dicionário de cache para objeto de domínio."""
    # Extrai campos básicos
    res = ProxyTestResult(
        status=data.get("status", "AGUARDANDO"),
        ip=data.get("ip"),
        country=data.get("country"),
        country_code=data.get("country_code"),
        country_name=data.get("country_name"),
        proxy_ip=data.get("proxy_ip"),
        proxy_country=data.get("proxy_country"),
        proxy_country_code=data.get("proxy_country_code"),
        error=data.get("error"),
        tested_at=data.get("tested_at", ""),
        cached=True
    )
    
    # Campos numéricos seguros
    ping_val = data.get("ping", data.get("ping_ms"))
    if ping_val is not None:
        res.ping_ms = safe_float(ping_val)
        
    ts_val = data.get("tested_at_ts")
    if ts_val is not None:
        res.tested_at_ts = safe_float(ts_val) or 0.0
        
    return res


def apply_cached_entry(entry: ProxyItem, cached_result: ProxyTestResult) -> ProxyItem:
    """Mescla resultado recuperado do cache ao registro corrente da proxy."""
    if not cached_result:
        return entry
    
    # Mescla results (novo resultado tem precedência mas mantemos campos do original se faltarem no novo?
    # No caso do cache, ele sobrescreve o estado inicial (que é vazio/aguardando).
    # Mas precisamos preservar o objeto original para manter referência se necessário?
    # ProxyItem é imutável? Não, dataclass mutável por padrão. Mas manager usa lista.
    # Vamos retornar nova cópia atualizada.
    
    # Se o cached_result já é um objeto completo, podemos usá-lo, 
    # mas precisamos garantir que não perdemos nada do entry.result atual se ele tivesse algo.
    # Geralmente entry.result está vazio na inicialização.
    
    from dataclasses import replace
    new_item = replace(entry, result=cached_result)
    
    # Atualiza host/port do item se estiverem disponíveis no resultado (mas ProxyTestResult não tem host/port do item, tem IP)
    # O cache antigo salvava host/port. O novo ProxyTestResult não tem esses campos.
    # O host/port do ProxyItem vem do Outbound config.
    # Se o teste detectou host/port diferente (raro), não temos onde guardar no Result.
    # Vamos assumir que host/port do item (config) prevalece.
    
    return new_item


def load_cache(cache_path: Path) -> Dict[str, ProxyTestResult]:
    """Carrega resultados persistidos anteriormente para acelerar novos testes."""
    try:
        raw_cache = cache_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}

    try:
        data = json.loads(raw_cache)
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {}

    cache_map: Dict[str, ProxyTestResult] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        uri = item.get("uri")
        if not isinstance(uri, str) or not uri.strip():
            continue
            
        # Parse result
        result = _parse_cached_result(item)
        cache_map[uri] = result
        
    return cache_map


def save_cache(cache_path: Path, entries: List[ProxyItem]) -> None:
    """Persiste a última bateria de testes para acelerar execuções futuras."""
    cache_dir = cache_path.parent
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    def prepare(item: ProxyItem) -> Optional[Dict[str, Any]]:
        if not isinstance(item, ProxyItem):
            return None
        
        entry = item.to_persistence_dict()
        
        # Validação simples final antes de salvar
        if not entry.get("uri"):
            return None
            
        return entry

    payload_entries = [prepared for entry in entries if (prepared := prepare(entry))]

    payload = {
        "version": CACHE_VERSION,
        "generated_at": format_timestamp(time.time()),
        "entries": payload_entries,
    }

    try:
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
