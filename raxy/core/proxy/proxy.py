#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ferramenta orientada a biblioteca para testar e criar pontes HTTP para proxys V2Ray/Xray.

O módulo expõe a classe :class:`Proxy`, que gerencia carregamento de links, testes
com filtragem opcional por país e criação de túneis HTTP locais utilizando Xray ou
V2Ray. Todo o comportamento é pensado para uso programático em outros módulos.
"""

from __future__ import annotations

import atexit
import base64
import json
import os
import re
import socket
import subprocess
import tempfile
import time
import ipaddress
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import urlparse, parse_qs, unquote, quote, urlsplit

__all__ = ["Proxy"]

try:
    import requests  # opcional: apenas se precisar de rede
except Exception:  # pragma: no cover - manter funcionalidade sem requests
    requests = None

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
except Exception:  # pragma: no cover - uso opcional de rich
    Console = None
    Table = None
    Text = None


class Proxy:
    """Gerencia uma coleção de proxys, com suporte a testes e criação de pontes HTTP."""

    DEFAULT_CACHE_FILENAME: str = "proxy_cache.json"
    CACHE_VERSION: int = 1

    STATUS_STYLES: Dict[str, str] = {
        "AGUARDANDO": "dim",
        "TESTANDO": "yellow",
        "OK": "bold green",
        "ERRO": "bold red",
        "FILTRADO": "cyan",
    }

    @dataclass(frozen=True)
    class Outbound:
        """Representa um outbound configurado para o Xray/V2Ray."""

        tag: str
        config: Dict[str, Any]

    def __init__(
        self,
        proxies: Optional[Iterable[str]] = None,
        sources: Optional[Iterable[str]] = None,
        *,
        country: Optional[str] = None,
        base_port: int = 54000,
        max_count: int = 0,
        use_console: bool = False,
        use_cache: bool = True,
        cache_path: Optional[Union[str, os.PathLike]] = None,
        command_output: bool = True,
        requests_session: Optional[Any] = None,
    ) -> None:
        """Inicializa o gerenciador carregando proxys, fontes e cache se necessário."""
        self.country_filter = country
        self.base_port = base_port
        self.max_count = max_count
        self.requests = requests_session or requests
        self.use_console = bool(use_console and Console)
        self.console = Console() if self.use_console and Console else None

        self._outbounds: List[Tuple[str, Proxy.Outbound]] = []
        self._entries: List[Dict[str, Any]] = []
        self._processes: List[subprocess.Popen] = []
        self._cfg_paths: List[Path] = []
        self._bridges: List[Tuple[str, int, str]] = []
        self._running = False
        self._atexit_registered = False
        self._parse_errors: List[str] = []

        self.use_cache = use_cache
        default_cache_path = Path(__file__).with_name(self.DEFAULT_CACHE_FILENAME)
        self.cache_path = Path(cache_path) if cache_path is not None else default_cache_path
        self._cache_entries: Dict[str, Dict[str, Any]] = {}
        self._stop_event = threading.Event()
        self._wait_thread: Optional[threading.Thread] = None
        self.command_output = bool(command_output)
        self._cache_available = False

        if self.use_cache:
            self._load_cache()

        if proxies:
            self.add_proxies(proxies)
        if sources:
            self.add_sources(sources)

        if self.use_cache and not self._entries and self._outbounds:
            self._prime_entries_from_cache()

    # ----------- utilidades básicas -----------

    def _make_base_entry(self, index: int, raw_uri: str, outbound: Proxy.Outbound) -> Dict[str, Any]:
        """Monta o dicionário padrão com as informações mínimas de um outbound."""
        return {
            "index": index,
            "tag": outbound.tag,
            "uri": raw_uri,
            "status": "AGUARDANDO",
            "host": "-",
            "port": None,
            "ip": "-",
            "country": "-",
            "country_code": None,
            "country_name": None,
            "ping": None,
            "error": None,
            "country_match": None,
            "tested_at": None,
            "tested_at_ts": None,
            "cached": False,
        }

    def _apply_cached_entry(self, entry: Dict[str, Any], cached: Dict[str, Any]) -> Dict[str, Any]:
        """Mescla dados recuperados do cache ao registro corrente da proxy."""
        if not cached:
            return entry
        entry = dict(entry)

        status = cached.get("status")
        if isinstance(status, str):
            entry["status"] = status

        if "host" in cached:
            entry["host"] = cached.get("host") or entry.get("host")
        if "port" in cached:
            port_value = cached.get("port")
            try:
                entry["port"] = int(port_value) if port_value is not None else entry.get("port")
            except (TypeError, ValueError):
                entry["port"] = entry.get("port")
        if "ip" in cached:
            entry["ip"] = cached.get("ip") or entry.get("ip")

        if "country" in cached:
            entry["country"] = cached.get("country") or entry.get("country")
        if "country_code" in cached:
            entry["country_code"] = cached.get("country_code") or entry.get("country_code")
        if "country_name" in cached:
            entry["country_name"] = cached.get("country_name") or entry.get("country_name")

        ping_value = cached.get("ping") if "ping" in cached else cached.get("ping_ms")
        if ping_value is not None:
            try:
                entry["ping"] = float(ping_value)
            except (TypeError, ValueError):
                entry["ping"] = entry.get("ping")

        if "error" in cached:
            entry["error"] = cached.get("error")

        tested_at_ts = cached.get("tested_at_ts")
        if tested_at_ts is not None:
            try:
                entry["tested_at_ts"] = float(tested_at_ts)
            except (TypeError, ValueError):
                entry["tested_at_ts"] = entry.get("tested_at_ts")
        if "tested_at" in cached:
            entry["tested_at"] = cached.get("tested_at") or entry.get("tested_at")

        entry["cached"] = True
        return entry

    def _register_new_outbound(self, raw_uri: str, outbound: Proxy.Outbound) -> None:
        """Atualiza as estruturas internas quando um novo outbound é aceito."""
        index = len(self._outbounds) - 1
        entry = self._make_base_entry(index, raw_uri, outbound)
        if self.use_cache and self._cache_entries:
            cached = self._cache_entries.get(raw_uri)
            if cached:
                entry = self._apply_cached_entry(entry, cached)
                entry["country_match"] = self.matches_country(entry, self.country_filter)
        if index >= len(self._entries):
            self._entries.append(entry)
        else:
            self._entries[index] = entry

    def _prime_entries_from_cache(self) -> None:
        """Reconstrói os registros a partir do cache sem repetir parsing."""
        if not self.use_cache or not self._cache_entries:
            return
        rebuilt: List[Dict[str, Any]] = []
        for idx, (raw_uri, outbound) in enumerate(self._outbounds):
            entry = self._make_base_entry(idx, raw_uri, outbound)
            cached = self._cache_entries.get(raw_uri)
            if cached:
                entry = self._apply_cached_entry(entry, cached)
                entry["country_match"] = self.matches_country(entry, self.country_filter)
            rebuilt.append(entry)
        self._entries = rebuilt

    def _format_timestamp(self, ts: float) -> str:
        """Retorna carimbo de data no formato ISO 8601 UTC sem microssegundos."""
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        iso = dt.replace(microsecond=0).isoformat()
        return iso.replace("+00:00", "Z")

    def _load_cache(self) -> None:
        """Carrega resultados persistidos anteriormente para acelerar novos testes."""
        if not self.use_cache:
            return
        self._cache_available = False
        try:
            raw_cache = self.cache_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError:
            return

        try:
            data = json.loads(raw_cache)
        except json.JSONDecodeError:
            return

        if not isinstance(data, dict):
            return
        entries = data.get("entries")
        if not isinstance(entries, list):
            return

        cache_map: Dict[str, Dict[str, Any]] = {}
        for item in entries:
            if not isinstance(item, dict):
                continue
            uri = item.get("uri")
            if not isinstance(uri, str) or not uri.strip():
                continue
            cache_map[uri] = item

        self._cache_entries = cache_map
        if cache_map:
            self._cache_available = True

    def _save_cache(self, entries: List[Dict[str, Any]]) -> None:
        """Persiste a última bateria de testes para acelerar execuções futuras."""
        if not self.use_cache:
            return
        cache_dir = self.cache_path.parent
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        payload_entries: List[Dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            uri = entry.get("uri")
            if not isinstance(uri, str) or not uri.strip():
                continue
            tested_ts = entry.get("tested_at_ts")
            if isinstance(tested_ts, (int, float)):
                tested_at_iso = self._format_timestamp(float(tested_ts))
            else:
                tested_ts = time.time()
                entry["tested_at_ts"] = tested_ts
                tested_at_iso = self._format_timestamp(tested_ts)
                if not entry.get("tested_at"):
                    entry["tested_at"] = tested_at_iso

            payload_entries.append({
                "uri": uri,
                "tag": entry.get("tag"),
                "status": entry.get("status"),
                "host": entry.get("host"),
                "port": entry.get("port"),
                "ip": entry.get("ip"),
                "country": entry.get("country"),
                "country_code": entry.get("country_code"),
                "country_name": entry.get("country_name"),
                "ping": entry.get("ping"),
                "error": entry.get("error"),
                "tested_at": entry.get("tested_at") or tested_at_iso,
                "tested_at_ts": tested_ts,
            })

        payload = {
            "version": self.CACHE_VERSION,
            "generated_at": self._format_timestamp(time.time()),
            "entries": payload_entries,
        }

        try:
            self.cache_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass
        else:
            self._cache_entries = {item["uri"]: item for item in payload_entries}
            self._cache_available = bool(payload_entries)

    @staticmethod
    def _b64decode_padded(value: str) -> bytes:
        """Decodifica base64 tolerando strings sem padding."""
        value = value.strip()
        missing = (-len(value)) % 4
        if missing:
            value += "=" * missing
        return base64.urlsafe_b64decode(value)

    @staticmethod
    def _sanitize_tag(tag: Optional[str], fallback: str) -> str:
        """Normaliza tags para algo seguro de ser usado em arquivos ou logs."""
        if not tag:
            return fallback
        tag = re.sub(r"[^\w\-\.]+", "_", tag)
        return tag[:48] or fallback

    @staticmethod
    def _decode_bytes(data: bytes, *, encoding_hint: Optional[str] = None) -> str:
        """Converte bytes em texto testando codificações comuns."""
        if not isinstance(data, (bytes, bytearray)):
            return str(data)
        encodings = []
        if encoding_hint:
            encodings.append(encoding_hint)
        encodings.extend(["utf-8", "utf-8-sig", "latin-1"])
        tried = set()
        for enc in encodings:
            if not enc or enc in tried:
                continue
            tried.add(enc)
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    def _read_source_text(self, source: str) -> str:
        """Obtém conteúdo bruto de um arquivo local ou URL contendo proxys."""
        if re.match(r"^https?://", source, re.I):
            if self.requests is None:
                raise RuntimeError("O pacote requests não está disponível para baixar URLs de proxy.")
            resp = self.requests.get(source, timeout=30)
            resp.raise_for_status()
            return self._decode_bytes(resp.content, encoding_hint=resp.encoding or None)
        path = Path(source)
        return self._decode_bytes(path.read_bytes())

    @staticmethod
    def _shutil_which(cmd: str) -> Optional[str]:
        """Localiza um executável equivalente ao comportamento de shutil.which."""
        paths = os.environ.get("PATH", "").split(os.pathsep)
        exts = [""]
        if os.name == "nt":
            exts = os.environ.get("PATHEXT", ".EXE;.BAT;.CMD").lower().split(";")
        for directory in paths:
            candidate = Path(directory) / cmd
            if candidate.exists() and candidate.is_file():
                return str(candidate)
            if os.name == "nt":
                base = Path(directory) / cmd
                for ext in exts:
                    alt = base.with_suffix(ext)
                    if alt.exists() and alt.is_file():
                        return str(alt)
        return None

    @classmethod
    def _which_xray(cls) -> str:
        """Descobre o binário do Xray/V2Ray respeitando variáveis de ambiente."""
        env_path = os.environ.get("XRAY_PATH")
        if env_path and Path(env_path).exists():
            return env_path
        for candidate in ("xray", "xray.exe", "v2ray", "v2ray.exe"):
            found = cls._shutil_which(candidate)
            if found:
                return found
        raise FileNotFoundError(
            "Não foi possível localizar o binário do Xray/V2Ray. Instale o xray-core ou configure XRAY_PATH."
        )

    @staticmethod
    def _format_destination(host: Optional[str], port: Optional[int]) -> str:
        """Monta representação amigável para host:porta exibida em tabelas."""
        if not host or host == "-":
            return "-"
        if port is None:
            return host
        return f"{host}:{port}"

    @staticmethod
    def matches_country(entry: Dict[str, Any], desired: Optional[str]) -> bool:
        """Valida se o registro atende ao filtro de país solicitado."""
        if not desired:
            return True
        desired_norm = desired.strip().casefold()
        if not desired_norm:
            return True

        candidates: List[str] = []
        for key in ("country", "country_code", "country_name"):
            value = entry.get(key)
            if not value:
                continue
            value = str(value).strip()
            if not value or value == "-":
                continue
            candidates.append(value)

        for value in candidates:
            if value.casefold() == desired_norm:
                return True
        for value in candidates:
            norm = value.casefold()
            if desired_norm in norm or norm in desired_norm:
                return True
        return False

    # ----------- carregamento de proxys -----------

    def add_proxies(self, proxies: Iterable[str]) -> int:
        """Adiciona proxys a partir de URIs completos (ss, vmess, vless, trojan)."""

        added = 0
        for raw in proxies:
            if raw is None:
                continue
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            try:
                outbound = self._parse_uri_to_outbound(line)
            except Exception as exc:
                self._parse_errors.append(f"Linha ignorada: {line[:80]} -> {exc}")
                continue
            self._outbounds.append((line, outbound))
            self._register_new_outbound(line, outbound)
            added += 1
            if self.max_count and len(self._outbounds) >= self.max_count:
                break
        return added

    def add_sources(self, sources: Iterable[str]) -> int:
        """Carrega proxys de arquivos locais ou URLs linha a linha."""

        added = 0
        for src in sources:
            text = self._read_source_text(src)
            lines = [ln.strip() for ln in text.splitlines()]
            added += self.add_proxies(lines)
        return added

    # ----------- parsing -----------

    def _parse_uri_to_outbound(self, uri: str) -> Proxy.Outbound:
        """Direciona o link para o parser adequado de acordo com o esquema."""
        uri = uri.strip()
        if not uri or uri.startswith("#") or uri.startswith("//"):
            raise ValueError("Linha vazia ou comentário.")
        match = re.match(r"^([a-z0-9]+)://", uri, re.I)
        if not match:
            raise ValueError(f"Esquema desconhecido na linha: {uri[:80]}")
        scheme = match.group(1).lower()
        parser = {
            "ss": self._parse_ss,
            "vmess": self._parse_vmess,
            "vless": self._parse_vless,
            "trojan": self._parse_trojan,
        }.get(scheme)
        if parser is None:
            raise ValueError(f"Esquema não suportado: {scheme}")
        return parser(uri)

    def _parse_ss(self, uri: str) -> Proxy.Outbound:
        """Normaliza um link ``ss://`` incluindo casos em JSON inline."""
        frag = urlsplit(uri).fragment
        tag = self._sanitize_tag(unquote(frag) if frag else None, "ss")

        payload = uri.strip()[5:]
        stripped_payload = payload.split('#')[0]

        try:
            decoded_preview = self._decode_bytes(self._b64decode_padded(stripped_payload))
        except Exception:
            decoded_preview = None

        if decoded_preview:
            text_preview = decoded_preview.strip()
            if text_preview.startswith('{') and text_preview.endswith('}'):
                try:
                    data_json = json.loads(text_preview)
                except json.JSONDecodeError:
                    pass
                else:
                    if {
                        "server", "method"
                    }.issubset(data_json.keys()) or {
                        "address", "method"
                    }.issubset(data_json.keys()) or {
                        "server", "password"
                    }.issubset(data_json.keys()):
                        ss_host = data_json.get("server") or data_json.get("address")
                        ss_port_raw = data_json.get("server_port") or data_json.get("port")
                        ss_method = data_json.get("method") or data_json.get("cipher")
                        ss_password = data_json.get("password") or data_json.get("passwd") or ""
                        if not ss_host or not ss_port_raw or not ss_method:
                            raise ValueError("Link ss:// incompleto (server/port/method ausentes no JSON).")
                        try:
                            ss_port = int(str(ss_port_raw).strip())
                        except (TypeError, ValueError):
                            raise ValueError(f"Porta ss inválida: {ss_port_raw!r}")
                        return self.Outbound(tag, {
                            "tag": tag,
                            "protocol": "shadowsocks",
                            "settings": {
                                "servers": [{
                                    "address": ss_host,
                                    "port": ss_port,
                                    "method": ss_method,
                                    "password": ss_password,
                                }]
                            }
                        })

        # formato padrão SIP002
        at_split = stripped_payload.rsplit('@', 1)
        if len(at_split) != 2:
            raise ValueError("Formato ss:// inválido.")
        userinfo_b64, hostport = at_split
        userinfo = None
        try:
            userinfo = self._decode_bytes(self._b64decode_padded(userinfo_b64))
        except Exception as exc:
            raise ValueError(f"Falha no base64 do ss://: {exc}") from exc
        if ':' not in userinfo:
            raise ValueError("Formato userinfo ss:// inválido (esperado method:password).")
        method, password = userinfo.split(':', 1)
        if ':' not in hostport:
            raise ValueError("Host ou porta ausentes no link ss://.")
        host, port_raw = hostport.split(':', 1)
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ValueError(f"Porta ss inválida: {port_raw!r}") from exc

        config = {
            "tag": tag,
            "protocol": "shadowsocks",
            "settings": {
                "servers": [{
                    "address": host,
                    "port": port,
                    "method": method,
                    "password": password,
                }]
            }
        }
        return self.Outbound(tag, config)

    def _parse_vmess(self, uri: str) -> Proxy.Outbound:
        """Converte links ``vmess://`` com conteúdo base64 para outbounds."""
        payload = uri.strip()[8:]
        try:
            decoded = self._decode_bytes(self._b64decode_padded(payload))
        except Exception as exc:
            raise ValueError(f"Erro ao decodificar vmess://: {exc}") from exc
        try:
            data = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON inválido em vmess://: {exc}") from exc
        return self._vmess_outbound_from_dict(data)

    def _vmess_outbound_from_dict(self, data: Dict[str, Any], *, tag_fallback: str = "vmess") -> Proxy.Outbound:
        """Adapta o dicionário decodificado de vmess para a estrutura do Xray."""
        tag = self._sanitize_tag(data.get("ps"), tag_fallback)

        host = data.get("add") or data.get("address")
        port_raw = data.get("port", 0)
        try:
            port = int(str(port_raw).strip())
        except (TypeError, ValueError):
            raise ValueError(f"Porta vmess inválida: {port_raw!r}")

        uuid = data.get("id")
        if not host or not port or not uuid:
            raise ValueError("vmess:// incompleto (host/port/id).")

        alter_id = data.get("aid", 0)
        try:
            alter_id = int(str(alter_id).strip() or "0")
        except (TypeError, ValueError):
            alter_id = 0

        net = str(data.get("net") or data.get("network") or "tcp").lower()
        tls_flag = str(data.get("tls") or data.get("security") or "").lower()
        tls = tls_flag == "tls"
        security = "tls" if tls else "none"

        sni = data.get("sni") or data.get("host")
        path = data.get("path") or "/"
        host_header = data.get("host")

        if net == "ws":
            transport = {
                "network": "ws",
                "wsSettings": {
                    "path": path or "/",
                    "headers": {"Host": host_header} if host_header else {}
                }
            }
        elif net == "grpc":
            service_name = data.get("serviceName") or (path or "/").lstrip("/")
            transport = {
                "network": "grpc",
                "grpcSettings": {"serviceName": service_name}
            }
        else:
            transport = {"network": "tcp"}

        scy = data.get("scy") or "auto"

        outbound_config = {
            "tag": tag,
            "protocol": "vmess",
            "settings": {
                "vnext": [{
                    "address": host,
                    "port": port,
                    "users": [{
                        "id": uuid,
                        "alterId": alter_id,
                        "security": scy
                    }]
                }]
            },
            "streamSettings": {
                "security": security,
                **transport
            }
        }

        if tls and sni:
            outbound_config["streamSettings"]["tlsSettings"] = {"serverName": sni}

        return self.Outbound(tag, outbound_config)

    def _parse_vless(self, uri: str) -> Proxy.Outbound:
        """Converte links ``vless://`` adicionando suporte a transportes modernos."""
        p = urlparse(uri)
        tag = self._sanitize_tag(unquote(p.fragment) if p.fragment else None, "vless")
        uuid = p.username
        host = p.hostname
        port = p.port
        q = parse_qs(p.query or "")
        flow = q.get("flow", [""])[0]
        security = q.get("security", ["none"])[0]
        sni = q.get("sni", [None])[0]
        alpn = q.get("alpn", [])
        net = q.get("type", ["tcp"])[0]
        path = q.get("path", ["/"])[0]
        host_header = q.get("host", [None])[0]
        service_name = q.get("serviceName", [""])[0]

        if not uuid or not host or not port:
            raise ValueError("vless:// incompleto (uuid/host/port).")

        transport: Dict[str, Any]
        if net == "ws":
            transport = {"network": "ws", "wsSettings": {
                "path": path,
                "headers": {"Host": host_header} if host_header else {}
            }}
        elif net == "grpc":
            transport = {"network": "grpc", "grpcSettings": {"serviceName": service_name}}
        else:
            transport = {"network": "tcp"}

        stream = {"security": "none", **transport}
        if security in ("tls", "reality"):
            stream["security"] = security
            tls_key = "tlsSettings" if security == "tls" else "realitySettings"
            tls_settings: Dict[str, Any] = {}
            if sni:
                tls_settings["serverName"] = sni
            if alpn:
                tls_settings["alpn"] = alpn
            stream[tls_key] = tls_settings

        outbound = {
            "tag": tag,
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": host,
                    "port": port,
                    "users": [{
                        "id": uuid,
                        "encryption": q.get("encryption", ["none"])[0],
                        "flow": flow,
                    }]
                }]
            },
            "streamSettings": stream
        }
        return self.Outbound(tag, outbound)

    def _parse_trojan(self, uri: str) -> Proxy.Outbound:
        """Converte links ``trojan://`` assegurando parâmetros TLS e transporte."""
        p = urlparse(uri)
        tag = self._sanitize_tag(unquote(p.fragment) if p.fragment else None, "trojan")
        password = unquote(p.username or "")
        host = p.hostname
        port = p.port
        q = parse_qs(p.query or "")
        security = (q.get("security", ["tls"])[0]).lower()
        sni = q.get("sni", [None])[0]
        alpn = q.get("alpn", [])
        net = (q.get("type", ["tcp"])[0]).lower()
        path = q.get("path", ["/"])[0]
        host_header = q.get("host", [None])[0]
        service_name = q.get("serviceName", [""])[0]

        if not password or not host or not port:
            raise ValueError("trojan:// incompleto (password/host/port).")

        if net == "ws":
            transport: Dict[str, Any] = {
                "network": "ws",
                "wsSettings": {
                    "path": path,
                    "headers": {"Host": host_header} if host_header else {}
                }
            }
        elif net == "grpc":
            transport = {"network": "grpc", "grpcSettings": {"serviceName": service_name}}
        else:
            transport = {"network": "tcp"}

        stream: Dict[str, Any] = {"security": "none", **transport}
        if security in ("tls", "reality"):
            stream["security"] = security
            tls_key = "tlsSettings" if security == "tls" else "realitySettings"
            tls_settings: Dict[str, Any] = {}
            if sni:
                tls_settings["serverName"] = sni
            if alpn:
                tls_settings["alpn"] = alpn
            stream[tls_key] = tls_settings

        outbound = {
            "tag": tag,
            "protocol": "trojan",
            "settings": {
                "servers": [{
                    "address": host,
                    "port": port,
                    "password": password,
                    "flow": ""
                }]
            },
            "streamSettings": stream
        }
        return self.Outbound(tag, outbound)

    # ----------- verificação e filtros -----------

    def _outbound_host_port(self, outbound: Proxy.Outbound) -> Tuple[str, int]:
        """Extrai host e porta reais do outbound conforme o protocolo."""
        proto = outbound.config.get("protocol")
        settings = outbound.config.get("settings", {})
        host = None
        port = None
        if proto == "shadowsocks":
            server = settings.get("servers", [{}])[0]
            host = server.get("address")
            port = server.get("port")
        elif proto in ("vmess", "vless"):
            vnext = settings.get("vnext", [{}])[0]
            host = vnext.get("address")
            port = vnext.get("port")
        elif proto == "trojan":
            server = settings.get("servers", [{}])[0]
            host = server.get("address")
            port = server.get("port")
        else:
            raise ValueError(f"Protocolo não suportado para teste: {proto}")

        if host is None or port is None:
            raise ValueError(f"Host/port ausentes no outbound {outbound.tag} ({proto}).")
        try:
            return host, int(str(port).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Porta inválida no outbound {outbound.tag}: {port!r}") from exc

    @staticmethod
    def _is_public_ip(ip: str) -> bool:
        """Retorna ``True`` se o IP for público e roteável pela Internet."""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return not (
            addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast or addr.is_link_local
        )

    def _lookup_country(self, ip: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
        """Consulta informações de localização do IP usando ipinfo.io."""
        if not ip or self.requests is None or not self._is_public_ip(ip):
            return None
        try:
            encoded = quote(ip, safe="")
            resp = self.requests.get(f"https://ipinfo.io/{encoded}", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            country_code = data.get("country")
            if isinstance(country_code, str):
                country_code = (country_code.strip() or None)
                if country_code:
                    country_code = country_code.upper()
            country_name = data.get("country_name")
            if isinstance(country_name, str):
                country_name = country_name.strip() or None
            label = country_name or country_code
            if not (label or country_code or country_name):
                return None
            return {
                "name": country_name,
                "code": country_code,
                "label": label,
            }
        except Exception:
            return None

    @staticmethod
    def _measure_tcp_ping(host: str, port: int, timeout: float = 5.0) -> float:
        """Calcula o tempo de conexão TCP em milissegundos."""
        start = time.perf_counter()
        with socket.create_connection((host, port), timeout=timeout):
            end = time.perf_counter()
        return (end - start) * 1000.0

    def _test_outbound(self, raw_uri: str, outbound: Proxy.Outbound) -> Dict[str, Any]:
        """Executa medições para um outbound específico retornando métricas."""
        result: Dict[str, Any] = {
            "tag": outbound.tag,
            "protocol": outbound.config.get("protocol"),
            "uri": raw_uri,
        }
        try:
            host, port = self._outbound_host_port(outbound)
        except Exception as exc:
            result["error"] = f"host/port não identificados: {exc}"
            return result

        result["host"] = host
        result["port"] = port

        try:
            ping_ms = self._measure_tcp_ping(host, port)
            result["ping_ms"] = ping_ms
        except Exception as exc:
            result["error"] = f"conexão TCP falhou: {exc}".strip()

        try:
            infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except Exception:
            infos = []
        ip = None
        ipv6 = None
        for info in infos:
            family, *_rest, sockaddr = info
            address = sockaddr[0]
            if family == socket.AF_INET:
                ip = address
                break
            if ipv6 is None and family == socket.AF_INET6:
                ipv6 = address
        result["ip"] = ip or ipv6

        country_info = self._lookup_country(result.get("ip"))
        if country_info:
            label = country_info.get("label")
            if label:
                result["country"] = label
            code = country_info.get("code")
            if code:
                result["country_code"] = code
            name = country_info.get("name")
            if name:
                result["country_name"] = name

        return result

    def _perform_health_checks(
        self,
        outbounds: List[Tuple[str, Proxy.Outbound]],
        *,
        country_filter: Optional[str] = None,
        emit_progress: Optional[Any] = None,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """Percorre os outbounds testando conectividade, ping e país."""
        entries: List[Dict[str, Any]] = []
        total = len(outbounds)
        reuse_cache = self.use_cache and not force_refresh

        for idx, (raw, outbound) in enumerate(outbounds, start=1):
            zero_index = idx - 1
            entry = self._make_base_entry(zero_index, raw, outbound)
            cached_data = self._cache_entries.get(raw) if reuse_cache else None

            if cached_data:
                entry = self._apply_cached_entry(entry, cached_data)
                entry["country_match"] = self.matches_country(entry, country_filter)
                if country_filter and entry.get("status") == "OK" and not entry["country_match"]:
                    entry["status"] = "FILTRADO"
                    detected_country = (
                        entry.get("country")
                        or entry.get("country_code")
                        or entry.get("country_name")
                        or "-"
                    )
                    entry["error"] = f"Filtro de país '{country_filter}': detectado {detected_country}"
                entries.append(entry)
                if emit_progress is not None:
                    destino = self._format_destination(entry.get("host"), entry.get("port"))
                    ping_preview = entry.get("ping")
                    ping_fmt = f"{ping_preview:.1f} ms" if isinstance(ping_preview, (int, float)) else "-"
                    should_display = not (country_filter and entry.get("status") == "FILTRADO")
                    if should_display:
                        status_fmt = {
                            "OK": "[bold green]OK[/]",
                            "ERRO": "[bold red]ERRO[/]",
                            "TESTANDO": "[yellow]TESTANDO[/]",
                            "AGUARDANDO": "[dim]AGUARDANDO[/]",
                            "FILTRADO": "[cyan]FILTRADO[/]",
                        }.get(entry["status"], entry["status"])
                        cache_note = ""
                        if entry.get("cached"):
                            cache_note = " [dim](cache)[/]" if Console else " (cache)"
                        emit_progress.print(
                            f"[{idx}/{total}] {status_fmt}{cache_note} [bold]{entry['tag']}[/] -> "
                            f"{destino} | IP: {entry.get('ip') or '-'} | "
                            f"País: {entry.get('country') or '-'} | Ping: {ping_fmt}"
                        )
                        if entry.get("error"):
                            emit_progress.print(f"    [dim]Motivo: {entry['error']}[/]")
                continue

            try:
                preview_host, preview_port = self._outbound_host_port(outbound)
            except Exception:
                preview_host = None
                preview_port = None
            if preview_host:
                entry["host"] = preview_host
            if preview_port is not None:
                entry["port"] = preview_port

            entry["status"] = "TESTANDO"

            result = self._test_outbound(raw, outbound)
            finished_at = time.time()
            entry["host"] = result.get("host") or entry["host"]
            if result.get("port") is not None:
                entry["port"] = result.get("port")
            entry["ip"] = result.get("ip") or entry["ip"]
            entry["country"] = result.get("country") or entry["country"]
            entry["country_code"] = result.get("country_code") or entry.get("country_code")
            entry["country_name"] = result.get("country_name") or entry.get("country_name")
            entry["ping"] = result.get("ping_ms")
            entry["tested_at_ts"] = finished_at
            entry["tested_at"] = self._format_timestamp(finished_at)

            entry["country_match"] = self.matches_country(entry, country_filter)

            if "ping_ms" in result:
                entry["status"] = "OK"
                entry["error"] = None
            else:
                entry["status"] = "ERRO"
                entry["error"] = result.get("error")

            if country_filter and entry["status"] == "OK" and not entry["country_match"]:
                entry["status"] = "FILTRADO"
                detected_country = (
                    entry.get("country")
                    or entry.get("country_code")
                    or entry.get("country_name")
                    or "-"
                )
                entry["error"] = f"Filtro de país '{country_filter}': detectado {detected_country}"

            entries.append(entry)

            if emit_progress is not None:
                destino = self._format_destination(entry.get("host"), entry.get("port"))
                ping_preview = entry.get("ping")
                ping_fmt = f"{ping_preview:.1f} ms" if isinstance(ping_preview, (int, float)) else "-"
                should_display = not (country_filter and entry.get("status") == "FILTRADO")
                if should_display:
                    status_fmt = {
                        "OK": "[bold green]OK[/]",
                        "ERRO": "[bold red]ERRO[/]",
                        "TESTANDO": "[yellow]TESTANDO[/]",
                        "AGUARDANDO": "[dim]AGUARDANDO[/]",
                        "FILTRADO": "[cyan]FILTRADO[/]",
                    }.get(entry["status"], entry["status"])
                    emit_progress.print(
                        f"[{idx}/{total}] {status_fmt} [bold]{entry['tag']}[/] -> "
                        f"{destino} | IP: {entry.get('ip') or '-'} | "
                        f"País: {entry.get('country') or '-'} | Ping: {ping_fmt}"
                    )
                    if entry["error"]:
                        emit_progress.print(f"    [dim]Motivo: {entry['error']}[/]")

        return entries

    # ----------- interface pública -----------

    @property
    def entries(self) -> List[Dict[str, Any]]:
        """Retorna os registros carregados ou decorrentes dos últimos testes."""
        return self._entries

    @property
    def parse_errors(self) -> List[str]:
        """Lista de linhas ignoradas ao interpretar os links informados."""
        return list(self._parse_errors)

    def test(
        self,
        *,
        country: Optional[str] = None,
        verbose: Optional[bool] = None,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """Executa medições de todos os outbounds e atualiza o cache local."""
        if not self._outbounds:
            raise RuntimeError("Nenhuma proxy carregada para testar.")

        country_filter = country if country is not None else self.country_filter
        emit = self.console if (self.console is not None and (verbose is None or verbose)) else None
        entries = self._perform_health_checks(
            self._outbounds,
            country_filter=country_filter,
            emit_progress=emit,
            force_refresh=force_refresh,
        )
        self._entries = entries
        self.country_filter = country_filter

        self._save_cache(entries)

        if self.console is not None and (verbose is None or verbose):
            self._render_test_summary(entries, country_filter)

        return entries

    def _render_test_summary(self, entries: List[Dict[str, Any]], country_filter: Optional[str]) -> None:
        """Exibe relatório amigável via Rich quando disponível."""
        if not self.console or Table is None:
            return
        table_entries = entries
        if country_filter:
            table_entries = [entry for entry in entries if entry.get("country_match")]

        self.console.print()
        self.console.rule("Tabela final")
        if table_entries:
            self.console.print(self._render_test_table(table_entries))
        else:
            self.console.print(
                f"[yellow]Nenhuma proxy corresponde ao filtro de país '{country_filter}'.[/]"
            )

        success = sum(1 for entry in entries if entry.get("status") == "OK")
        fail = sum(1 for entry in entries if entry.get("status") == "ERRO")
        filtered = sum(1 for entry in entries if entry.get("status") == "FILTRADO")

        self.console.print()
        self.console.rule("Resumo do Teste")
        summary_parts = [
            f"[bold cyan]Total:[/] {len(entries)}",
            f"[bold green]Sucesso:[/] {success}",
            f"[bold red]Falhas:[/] {fail}",
        ]
        if filtered:
            summary_parts.append(f"[cyan]Filtradas:[/] {filtered}")
        self.console.print("    ".join(summary_parts))

        failed_entries = [
            entry for entry in entries
            if entry.get("status") == "ERRO" and entry.get("error")
        ]
        if failed_entries:
            self.console.print()
            self.console.print("[bold red]Detalhes das falhas:[/]")
            for entry in failed_entries:
                self.console.print(f" - [bold]{entry.get('tag') or '-'}[/]: {entry['error']}")

    @staticmethod
    def _render_test_table(entries: List[Dict[str, Any]]):
        """Gera uma tabela Rich com o resultado dos testes."""
        if Table is None:
            raise RuntimeError("render_test_table requer a biblioteca 'rich'.")
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Tag", no_wrap=True)
        table.add_column("Destino", overflow="fold")
        table.add_column("IP", no_wrap=True)
        table.add_column("País", no_wrap=True)
        table.add_column("Ping", justify="right", no_wrap=True)
        for entry in entries:
            status = entry.get("status", "-")
            style = Proxy.STATUS_STYLES.get(status, "white")
            status_cell = Text(status, style=style) if Text else status
            host = entry.get("host")
            port = entry.get("port")
            destino = Proxy._format_destination(host, port)
            ping = entry.get("ping")
            ping_str = f"{ping:.1f} ms" if isinstance(ping, (int, float)) else "-"
            table.add_row(
                status_cell,
                (entry.get("tag") or "-")[:40],
                destino,
                entry.get("ip") or "-",
                entry.get("country") or "-",
                ping_str,
            )
        return table

    def start(
        self,
        *,
        country: Optional[str] = None,
        auto_test: bool = True,
        wait: bool = False,
    ) -> List[str]:
        """Cria pontes HTTP locais para as proxys aprovadas opcionalmente testando antes."""
        if self._running:
            raise RuntimeError("As pontes já estão em execução. Chame stop() antes de iniciar novamente.")
        if not self._outbounds:
            raise RuntimeError("Nenhuma proxy carregada para iniciar.")

        country_filter = country if country is not None else self.country_filter
        # if auto_test and (not self._entries or country_filter != self.country_filter):
        #     self.test(country=country_filter, verbose=self.use_console)
        if country_filter is not None and country_filter != self.country_filter:
            # reutiliza testes existentes, apenas reforça a filtragem
            self.country_filter = country_filter

        if auto_test and self.use_cache and not self._cache_available:
            self.test(country=country_filter, verbose=self.use_console, force_refresh=True)
            country_filter = self.country_filter

        approved_entries = [entry for entry in self._entries if entry.get("status") == "OK"]
        if not approved_entries:
            raise RuntimeError("Nenhuma proxy aprovada para iniciar. Execute test() e verifique os resultados.")

        xray_bin = self._which_xray()

        self._stop_event.clear()
        port = self.base_port
        bridges: List[Tuple[str, int, str]] = []
        processes: List[subprocess.Popen] = []
        cfg_paths: List[Path] = []

        for entry in approved_entries:
            raw, outbound = self._outbounds[entry["index"]]
            cfg = self._make_xray_config_http_inbound(port, outbound)
            proc, cfg_path = self._launch_bridge(xray_bin, cfg, outbound.tag)
            processes.append(proc)
            cfg_paths.append(cfg_path)
            scheme = raw.split("://", 1)[0].lower()
            bridges.append((outbound.tag, port, scheme))
            port += 1

        self._processes = processes
        self._cfg_paths = cfg_paths
        self._bridges = bridges
        self._running = True

        if not self._atexit_registered:
            atexit.register(self.stop)
            self._atexit_registered = True

        if self.console is not None:
            self.console.print()
            self.console.rule("Pontes HTTP ativas")
            for tag, prt, scheme in bridges:
                self.console.print(f"[{scheme:6}] http://127.0.0.1:{prt}  ->  outbound '{tag}'")
            self.console.print()
            self.console.print("Pressione Ctrl+C para encerrar todas as pontes.")

        http_proxies = [f"http://127.0.0.1:{port}" for (_, port, _) in bridges]

        if wait:
            self.wait()
        else:
            self._start_wait_thread()

        return http_proxies

    def _start_wait_thread(self) -> None:
        """Dispara thread em segundo plano para monitorar processos iniciados."""
        if self._wait_thread and self._wait_thread.is_alive():
            return
        thread = threading.Thread(target=self._wait_loop_wrapper, name="ProxyWaitThread", daemon=True)
        self._wait_thread = thread
        thread.start()

    def _wait_loop_wrapper(self) -> None:
        """Executa ``wait`` capturando exceções para um término limpo da thread."""
        try:
            self.wait()
        except RuntimeError:
            # Nenhuma ponte ativa quando o wrapper inicia
            pass

    def wait(self) -> None:
        """Bloqueia até que todas as pontes terminem ou ``stop`` seja chamado."""
        if not self._running:
            raise RuntimeError("Nenhuma ponte ativa para aguardar.")
        try:
            while True:
                if self._stop_event.is_set():
                    break
                alive = False
                for proc in list(self._processes):
                    if proc.poll() is None:
                        alive = True
                    if proc.stdout:
                        line = proc.stdout.readline()
                        if line and ("warning" in line.lower() or "error" in line.lower()):
                            print(line.rstrip())
                if not alive:
                    print("Todos os processos xray finalizaram.")
                    break
                time.sleep(0.2)
        finally:
            self.stop()

    def stop(self) -> None:
        """Finaliza processos Xray ativos e limpa arquivos temporários."""
        self._stop_event.set()

        wait_thread = self._wait_thread
        caller_thread = threading.current_thread()

        if self._running:
            for proc in self._processes:
                try:
                    proc.terminate()
                except Exception:
                    pass
            for proc in self._processes:
                try:
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            for cfg_path in self._cfg_paths:
                try:
                    shutil.rmtree(cfg_path.parent, ignore_errors=True)
                except Exception:
                    pass
            self._processes = []
            self._cfg_paths = []
            self._bridges = []
            self._running = False
        else:
            # Garante que as listas estejam sempre limpas, mesmo após múltiplas chamadas a stop()
            self._processes = []
            self._cfg_paths = []
            self._bridges = []

        if wait_thread and wait_thread is not caller_thread:
            if wait_thread.is_alive():
                try:
                    wait_thread.join(timeout=1.0)
                except Exception:
                    pass
        self._wait_thread = None
        self._running = False

    def get_http_proxy(self) -> List[str]:
        """Retorna URLs HTTP locais das pontes em execução."""
        if not self._running:
            raise RuntimeError("Nenhuma ponte ativa. Chame start() primeiro.")
        return [f"http://127.0.0.1:{port}" for (_, port, _) in self._bridges]

    # ----------- geração e execução de config -----------

    def _make_xray_config_http_inbound(self, port: int, outbound: Proxy.Outbound) -> Dict[str, Any]:
        """Monta o arquivo de configuração do Xray para uma ponte HTTP local."""
        cfg = {
            "log": {"loglevel": "warning"},
            "inbounds": [{
                "tag": "http-in",
                "listen": "127.0.0.1",
                "port": port,
                "protocol": "http",
                "settings": {}
            }],
            "outbounds": [
                outbound.config,
                {"tag": "direct", "protocol": "freedom", "settings": {}},
                {"tag": "block", "protocol": "blackhole", "settings": {}}
            ],
            "routing": {
                "domainStrategy": "AsIs",
                "rules": [
                    {"type": "field", "outboundTag": outbound.tag, "network": "tcp,udp"}
                ]
            }
        }
        if "tag" not in cfg["outbounds"][0]:
            cfg["outbounds"][0]["tag"] = outbound.tag
        return cfg

    def _launch_bridge(self, xray_bin: str, cfg: Dict[str, Any], name: str) -> Tuple[subprocess.Popen, Path]:
        """Inicializa o processo Xray com configuração temporária para a ponte."""
        tmpdir = Path(tempfile.mkdtemp(prefix=f"xray_{name}_"))
        cfg_path = tmpdir / "config.json"
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        if self.command_output:
            stdout_target = subprocess.PIPE
            stderr_target = subprocess.STDOUT
        else:
            stdout_target = subprocess.DEVNULL
            stderr_target = subprocess.DEVNULL
        proc = subprocess.Popen(
            [xray_bin, "-config", str(cfg_path)],
            stdout=stdout_target,
            stderr=stderr_target,
            text=True,
            bufsize=1
        )
        return proc, cfg_path
