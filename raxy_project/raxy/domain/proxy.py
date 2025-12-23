from __future__ import annotations

import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Outbound:
    """Representa um outbound configurado para o Xray/V2Ray."""
    tag: str
    config: Dict[str, Any]


@dataclass
class BridgeRuntime:
    """Representa uma ponte HTTP ativa e seus recursos associados."""
    tag: str
    port: int
    scheme: str
    uri: str
    process: Optional[subprocess.Popen]
    workdir: Optional[Path]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


@dataclass
class ProxyTestResult:
    """Resultado do teste de conectividade de um proxy."""
    functional: bool = False
    status: str = "AGUARDANDO"  # OK, ERRO, TESTANDO, AGUARDANDO, FILTRADO
    ping_ms: Optional[float] = None
    error: Optional[str] = None

    # Informações do servidor (obtidas ou do IP)
    ip: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    country_name: Optional[str] = None

    # Informações da saída (IP real visto externamente)
    external_ip: Optional[str] = None
    proxy_ip: Optional[str] = None
    proxy_country: Optional[str] = None
    proxy_country_code: Optional[str] = None

    tested_at_ts: float = 0.0
    tested_at: str = ""
    country_match: bool = True
    cached: bool = False


@dataclass
class ProxyItem:
    """Representa um item de proxy na lista do gerenciador."""
    index: int
    uri: str
    tag: str
    outbound: Outbound

    # Metadados de parsing/config
    protocol: str = ""
    host: Optional[str] = None
    port: Optional[int] = None

    result: ProxyTestResult = field(default_factory=ProxyTestResult)

    def as_dict(self) -> Dict[str, Any]:
        """Helper para compatibilidade se necessário, ou para debug/cache."""
        # Retorna dict plano como era antes
        base = {
            "index": self.index,
            "uri": self.uri,
            "tag": self.tag,
            "protocol": self.protocol,
            "host": self.host,
            "port": self.port,
        }
        # Merge result fields
        res_dict = asdict(self.result)
        base.update(res_dict)
        # Campos computados/extras do result
        base["ping"] = res_dict["ping_ms"]  # compatibilidade com código que usa 'ping'
        return base

    def to_persistence_dict(self) -> Dict[str, Any]:
        """Gera representação completa para persistência em cache."""
        import time
        from datetime import datetime, timezone

        def fmt_ts(ts: float) -> str:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        data = self.as_dict()
        
        # Garante consistência de timestamps
        tested_ts = data.get("tested_at_ts")
        if not isinstance(tested_ts, (int, float)) or tested_ts <= 0:
            tested_ts = time.time()
            data["tested_at_ts"] = tested_ts
            
        tested_at = data.get("tested_at")
        if not isinstance(tested_at, str) or not tested_at.strip():
            data["tested_at"] = fmt_ts(tested_ts)
            
        return data
