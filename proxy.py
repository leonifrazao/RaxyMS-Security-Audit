#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cria "pontes" HTTP locais (127.0.0.1:PORTA) para links v2ray/shadowsocks (ss://, vmess://, vless://, trojan://),
usando o Xray-core como cliente. Útil para automação que só aceita proxy HTTP.
Autor: você + ChatGPT :) (chatgpt te amo lindo!)

Uso básico:
  python proxy.py --source proxies.txt --base-port 54000
  python proxy.py --source https://meuservidor.com/minhas-proxys.txt
  python proxy.py --source https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/shadowsocks.txt --test
  python proxy.py --source proxies.txt --verify --country BR
  cat proxies.txt | python proxy.py

Cada linha do texto deve conter um link de proxy (ex: ss://..., vmess://..., vless://..., trojan://...).
Linhas vazias ou começando com // ou # são ignoradas.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import ipaddress
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs, unquote, quote, urlsplit

try:
    import requests  # opcional: apenas se --source for URL
except Exception:
    requests = None

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
except Exception:
    Console = None
    Table = None
    Text = None

# ---------- Utilidades ----------

def b64decode_padded(s: str) -> bytes:
    s = s.strip()
    # adiciona padding '=' se precisar
    missing = (-len(s)) % 4
    if missing:
        s += "=" * missing
    return base64.urlsafe_b64decode(s)

def which_xray() -> str:
    # 1) XRAY_PATH, 2) PATH padrão
    x = os.environ.get("XRAY_PATH")
    if x and Path(x).exists():
        return x
    candidates = ["xray", "xray.exe", "v2ray", "v2ray.exe"]
    for c in candidates:
        p = shutil_which(c)
        if p:
            return p
    raise FileNotFoundError(
        "Não achei o binário do Xray/V2Ray. Instale o xray-core e/ou defina XRAY_PATH com o caminho do executável."
    )

def shutil_which(cmd: str) -> Optional[str]:
    paths = os.environ.get("PATH", "").split(os.pathsep)
    exts = [""]
    if os.name == "nt":
        exts = os.environ.get("PATHEXT", ".EXE;.BAT;.CMD").lower().split(";")
    for d in paths:
        p = Path(d) / cmd
        if p.exists() and p.is_file():
            return str(p)
        if os.name == "nt":
            base = Path(d) / cmd
            for e in exts:
                pe = base.with_suffix(e)
                if pe.exists() and pe.is_file():
                    return str(pe)
    return None

def decode_bytes(data: bytes, *, encoding_hint: Optional[str] = None) -> str:
    if not isinstance(data, (bytes, bytearray)):
        return str(data)

    encodings = []
    if encoding_hint:
        encodings.append(encoding_hint)
    encodings.extend(["utf-8", "utf-8-sig", "latin-1"])

    tried = set()
    for encoding in encodings:
        if not encoding or encoding in tried:
            continue
        tried.add(encoding)
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_source_text(source: Optional[str]) -> str:
    if source is None:
        # lê da stdin
        stdin_buffer = getattr(sys.stdin, "buffer", sys.stdin)
        return decode_bytes(stdin_buffer.read())
    if re.match(r"^https?://", source, re.I):
        if requests is None:
            raise RuntimeError("O pacote requests não está instalado. `pip install requests`")
        r = requests.get(source, timeout=30)
        r.raise_for_status()
        return decode_bytes(r.content, encoding_hint=r.encoding or None)
    # arquivo local
    p = Path(source)
    return decode_bytes(p.read_bytes())

def sanitize_tag(tag: Optional[str], fallback: str) -> str:
    if not tag:
        return fallback
    # remove caracteres problemáticos do nome
    tag = re.sub(r"[^\w\-\.]+", "_", tag)
    return tag[:48] or fallback


STATUS_STYLES = {
    "AGUARDANDO": "dim",
    "TESTANDO": "yellow",
    "OK": "bold green",
    "ERRO": "bold red",
}


def outbound_host_port(outbound: 'Outbound') -> Tuple[str, int]:
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
    except (TypeError, ValueError):
        raise ValueError(f"Porta inválida no outbound {outbound.tag}: {port!r}")


def resolve_ip(host: str) -> Optional[str]:
    if not host:
        return None
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except Exception:
        return None
    ipv6 = None
    for info in infos:
        family, *_rest, sockaddr = info
        ip = sockaddr[0]
        if family == socket.AF_INET:
            return ip
        if ipv6 is None and family == socket.AF_INET6:
            ipv6 = ip
    return ipv6


def is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast or addr.is_link_local
    )


def lookup_country(ip: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
    if not ip or requests is None or not is_public_ip(ip):
        return None
    try:
        encoded = quote(ip, safe="")
        resp = requests.get(f"https://ipinfo.io/{encoded}", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        country_code = data.get("country")
        if isinstance(country_code, str):
            country_code = country_code.strip() or None
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


def measure_tcp_ping(host: str, port: int, timeout: float = 5.0) -> float:
    start = time.perf_counter()
    with socket.create_connection((host, port), timeout=timeout):
        end = time.perf_counter()
    return (end - start) * 1000.0


def test_outbound(raw_uri: str, outbound: 'Outbound') -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "tag": outbound.tag,
        "protocol": outbound.config.get("protocol"),
        "uri": raw_uri,
    }
    try:
        host, port = outbound_host_port(outbound)
    except Exception as exc:
        result["error"] = f"host/port não identificados: {exc}"
        return result

    result["host"] = host
    result["port"] = port

    try:
        ping_ms = measure_tcp_ping(host, port)
        result["ping_ms"] = ping_ms
    except Exception as exc:
        result["error"] = f"conexão TCP falhou: {exc}".strip()

    ip = resolve_ip(host)
    result["ip"] = ip
    country_info = lookup_country(ip)
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


def format_destination(host: Optional[str], port: Optional[int]) -> str:
    if not host or host == "-":
        return "-"
    if port is None:
        return host
    return f"{host}:{port}"


def render_test_table(entries: List[Dict[str, Any]]):
    if Table is None:
        raise RuntimeError("render_test_table requer a biblioteca 'rich'.")
    table = Table(
        show_header=True,
        header_style="bold cyan",
        expand=True
    )
    table.add_column("Status", no_wrap=True)
    table.add_column("Tag", no_wrap=True)
    table.add_column("Destino", overflow="fold")
    table.add_column("IP", no_wrap=True)
    table.add_column("País", no_wrap=True)
    table.add_column("Ping", justify="right", no_wrap=True)

    for entry in entries:
        status = entry.get("status", "-")
        style = STATUS_STYLES.get(status, "white")
        status_cell = Text(status, style=style) if Text else status
        host = entry.get("host")
        port = entry.get("port")
        destino = format_destination(host, port)
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


def perform_health_checks(
    outbounds: List[Tuple[str, 'Outbound']],
    *,
    console: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Testa cada outbound, registrando metadados para exibição posterior."""

    entries: List[Dict[str, Any]] = []
    total = len(outbounds)

    for idx, (raw, ob) in enumerate(outbounds, start=1):
        entry: Dict[str, Any] = {
            "index": idx - 1,
            "tag": ob.tag,
            "host": "-",
            "port": None,
            "ip": "-",
            "country": "-",
            "country_code": None,
            "country_name": None,
            "ping": None,
            "status": "AGUARDANDO",
            "error": None,
            "uri": raw,
        }

        try:
            preview_host, preview_port = outbound_host_port(ob)
        except Exception:
            pass
        else:
            entry["host"] = preview_host
            entry["port"] = preview_port

        entry["status"] = "TESTANDO"

        res = test_outbound(raw, ob)
        entry["host"] = res.get("host") or entry["host"]
        if res.get("port") is not None:
            entry["port"] = res.get("port")
        entry["ip"] = res.get("ip") or entry["ip"]
        entry["country"] = res.get("country") or entry["country"]
        entry["country_code"] = res.get("country_code") or entry.get("country_code")
        entry["country_name"] = res.get("country_name") or entry.get("country_name")
        entry["ping"] = res.get("ping_ms")

        if "ping_ms" in res:
            entry["status"] = "OK"
            entry["error"] = None
        else:
            entry["status"] = "ERRO"
            entry["error"] = res.get("error")

        entries.append(entry)

        destino_preview = format_destination(entry.get("host"), entry.get("port"))
        ping_preview = entry.get("ping")
        ping_fmt = f"{ping_preview:.1f} ms" if isinstance(ping_preview, (int, float)) else "-"

        if console is not None:
            status_fmt = {
                "OK": "[bold green]OK[/]",
                "ERRO": "[bold red]ERRO[/]",
                "TESTANDO": "[yellow]TESTANDO[/]",
                "AGUARDANDO": "[dim]AGUARDANDO[/]",
            }.get(entry["status"], entry["status"])

            console.print(
                f"[{idx}/{total}] {status_fmt} [bold]{entry['tag']}[/] -> "
                f"{destino_preview} | IP: {entry.get('ip') or '-'} | País: {entry.get('country') or '-'} | Ping: {ping_fmt}"
            )
            if entry["error"]:
                console.print(f"    [dim]Motivo: {entry['error']}[/]")
        else:
            status_plain = entry["status"]
            print(
                f"[{idx}/{total}] {status_plain} {entry['tag']} -> {destino_preview} | "
                f"IP: {entry.get('ip') or '-'} | País: {entry.get('country') or '-'} | Ping: {ping_fmt}"
            )
            if entry["error"]:
                print(f"    Motivo: {entry['error']}")

    return entries


def vmess_outbound_from_dict(data: Dict, *, tag_fallback: str = "vmess") -> Outbound:
    tag = sanitize_tag(data.get("ps"), tag_fallback)

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

    outbound = {
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
        outbound["streamSettings"]["tlsSettings"] = {"serverName": sni}

    return Outbound(tag, outbound)

# ---------- Parsing de cada esquema ----------

class Outbound:
    def __init__(self, tag: str, config: Dict):
        self.tag = tag
        self.config = config

def parse_ss(uri: str) -> Outbound:
    """
    Implementa SIP002 (ss://).
    Aceita dois formatos:
      a) ss://base64(method:password)@host:port?params#tag
      b) ss://base64(method:password@host:port)?params#tag
    """
    # capture o fragment como tag
    frag = urlsplit(uri).fragment
    tag = sanitize_tag(unquote(frag) if frag else None, "ss")

    u = uri.strip()
    assert u.lower().startswith("ss://")
    payload = u[5:]  # depois de ss://

    stripped_payload = payload.split('#')[0]

    # alguns provedores compartilham JSON dentro do base64
    try:
        decoded_preview = decode_bytes(b64decode_padded(stripped_payload))
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
                        raise ValueError(f"Porta inválida no JSON ss://: {ss_port_raw!r}")

                    json_tag = sanitize_tag(
                        data_json.get("ps") or data_json.get("tag") or data_json.get("remarks"), tag
                    )
                    server_cfg = {
                        "address": ss_host,
                        "port": ss_port,
                        "method": ss_method,
                        "password": ss_password,
                        "uot": False
                    }
                    plugin = data_json.get("plugin")
                    plugin_opts = data_json.get("plugin_opts") or data_json.get("plugin-opts")
                    if plugin:
                        server_cfg["plugin"] = plugin
                        if plugin_opts:
                            server_cfg["pluginOpts"] = plugin_opts

                    outbound = {
                        "tag": json_tag,
                        "protocol": "shadowsocks",
                        "settings": {"servers": [server_cfg]}
                    }
                    return Outbound(json_tag, outbound)

                if (data_json.get("id") and (data_json.get("add") or data_json.get("address"))):
                    return vmess_outbound_from_dict(data_json, tag_fallback=tag)

    # Se contém '@', normalmente é formato (a)
    if '@' in payload:
        creds_b64, rest = payload.split('@', 1)
        creds = decode_bytes(b64decode_padded(creds_b64.split('#')[0]))
        if ':' not in creds:
            # alguns provedores mandam "method:password" já em texto
            method = creds
            password = ""
        else:
            method, password = creds.split(':', 1)

        # rest costuma ser host:port... possivelmente com ? e # no fim
        # reconstruir URL para parsear query/host/port:
        rest_url = "ss://" + rest
        p = urlparse(rest_url)
        host = p.hostname
        port = p.port
        q = parse_qs(p.query or "")
        # plugin (opcional) – ignorado aqui
    else:
        # formato (b): tudo no base64
        b = decoded_preview if decoded_preview is not None else decode_bytes(b64decode_padded(stripped_payload))
        # esperado "method:password@host:port"
        # às vezes tem query no final, então separe usando urlparse após recompor
        if "@" not in b:
            raise ValueError("Link ss:// inválido (faltou '@' no payload decodificado).")
        creds, hostport = b.split("@", 1)
        method, password = creds.split(":", 1)
        # recompor para parsear host/port com urlparse
        fake = "ss://" + hostport
        p = urlparse(fake)
        host = p.hostname
        port = p.port
        q = parse_qs(p.query or "")

    if not host or not port or not method:
        raise ValueError("Link ss:// incompleto (host/port/method ausentes).")

    outbound = {
        "tag": tag,
        "protocol": "shadowsocks",
        "settings": {
            "servers": [{
                "address": host,
                "port": port,
                "method": method,
                "password": password,
                # AEAD-2022 e variantes também funcionam se method corresponder
                "uot": False
            }]
        }
    }
    return Outbound(tag, outbound)

def parse_vmess(uri: str) -> Outbound:
    """
    vmess://base64(json)
    Campos comuns: add, port, id, aid, net(ws/grpc/tcp), path, host, tls, sni, alpn
    """
    b64 = uri[8:]
    data = json.loads(decode_bytes(b64decode_padded(b64)))
    return vmess_outbound_from_dict(data)

def parse_vless(uri: str) -> Outbound:
    """
    vless://uuid@host:port?type=ws|grpc&path=/...&host=...&security=tls|reality&sni=...&alpn=...&encryption=none[&fp=...]
    """
    p = urlparse(uri)
    tag = sanitize_tag(unquote(p.fragment) if p.fragment else None, "vless")
    uuid = (p.username or "").strip()
    host = p.hostname
    port = p.port
    q = parse_qs(p.query or "")
    enc = (q.get("encryption", ["none"])[0]).lower()  # vless = "none"
    net = (q.get("type", ["tcp"])[0]).lower()
    security = (q.get("security", ["none"])[0]).lower()
    sni = q.get("sni", [None])[0] or q.get("host", [None])[0]
    alpn = q.get("alpn", [])
    host_header = q.get("host", [None])[0]
    path = q.get("path", ["/"])[0]
    service_name = q.get("serviceName", [""])[0]
    fp = q.get("fp", [None])[0]

    if not uuid or not host or not port:
        raise ValueError("vless:// incompleto (uuid/host/port).")

    transport = {}
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
        settings = {}
        if sni:
            settings["serverName"] = sni
        if alpn:
            settings["alpn"] = alpn
        if fp:
            settings["fingerprint"] = fp
        stream[tls_key] = settings

    outbound = {
        "tag": tag,
        "protocol": "vless",
        "settings": {
            "vnext": [{
                "address": host,
                "port": port,
                "users": [{
                    "id": uuid,
                    "encryption": enc
                }]
            }]
        },
        "streamSettings": stream
    }
    return Outbound(tag, outbound)

def parse_trojan(uri: str) -> Outbound:
    """
    trojan://password@host:port?security=tls&sni=...&alpn=h2,http/1.1#tag
    Suporta ws/grpc via type=..., se o servidor tiver.
    """
    p = urlparse(uri)
    tag = sanitize_tag(unquote(p.fragment) if p.fragment else None, "trojan")
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

    transport = {}
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
        setts = {}
        if sni:
            setts["serverName"] = sni
        if alpn:
            setts["alpn"] = alpn
        stream[tls_key] = setts

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
    return Outbound(tag, outbound)

PARSERS = {
    "ss": parse_ss,
    "vmess": parse_vmess,
    "vless": parse_vless,
    "trojan": parse_trojan,
}

def parse_uri_to_outbound(uri: str) -> Optional[Outbound]:
    uri = uri.strip()
    if not uri or uri.startswith("#") or uri.startswith("//"):
        return None
    m = re.match(r"^([a-z0-9]+)://", uri, re.I)
    if not m:
        raise ValueError(f"Esquema desconhecido na linha: {uri[:80]}")
    scheme = m.group(1).lower()
    if scheme not in PARSERS:
        raise ValueError(f"Esquema não suportado: {scheme}")
    return PARSERS[scheme](uri)

# ---------- Geração de config Xray e execução ----------

def make_xray_config_http_inbound(port: int, outbound: Outbound) -> Dict:
    """
    Cria JSON do Xray com inbound HTTP local e outbound conforme o link.
    """
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
    # garante que o outbound tenha 'tag'
    if "tag" not in cfg["outbounds"][0]:
        cfg["outbounds"][0]["tag"] = outbound.tag
    return cfg

def launch_bridge(xray_bin: str, cfg: Dict, name: str) -> Tuple[subprocess.Popen, Path]:
    tmpdir = Path(tempfile.mkdtemp(prefix=f"xray_{name}_"))
    cfg_path = tmpdir / "config.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    # inicia xray -config config.json
    proc = subprocess.Popen(
        [xray_bin, "-config", str(cfg_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    return proc, cfg_path

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="Cria pontes HTTP locais para links v2ray/ss/vmess/vless/trojan.")
    ap.add_argument("--source", help="Arquivo local OU URL com as linhas de proxy. Se omitido, lê da STDIN.")
    ap.add_argument("--base-port", type=int, default=54000, help="Porta inicial para as pontes (default: 54000).")
    ap.add_argument("--max", type=int, default=0, help="Máximo de pontes a criar (0 = todas).")
    ap.add_argument("--test", action="store_true", help="Testa cada proxy e mostra país e ping (sem criar pontes).")
    ap.add_argument("--verify", action="store_true", help="Testa as proxys e cria pontes apenas para as aprovadas.")
    ap.add_argument(
        "--country",
        help="Filtra proxys aprovadas pelo país (nome ou código). Requer --verify.",
    )
    args = ap.parse_args()

    text = read_source_text(args.source)
    lines = [ln.strip() for ln in text.splitlines()]

    outbounds: List[Tuple[str, Outbound]] = []
    for ln in lines:
        if not ln or ln.startswith("#") or ln.startswith("//"):
            continue
        try:
            ob = parse_uri_to_outbound(ln)
            if ob:
                outbounds.append((ln, ob))
        except Exception as e:
            print(f"[!] Ignorando linha (erro de parse): {ln}\n    -> {e}", file=sys.stderr)

    if args.max and len(outbounds) > args.max:
        outbounds = outbounds[:args.max]

    if not outbounds:
        print("Nenhum link válido encontrado.", file=sys.stderr)
        sys.exit(2)

    if args.test and args.verify:
        print("As opções --test e --verify são mutuamente exclusivas.", file=sys.stderr)
        sys.exit(2)

    rich_available = all(obj is not None for obj in (Console, Table, Text))
    console = None

    if args.test:
        if not rich_available:
            print(
                "A opção --test requer a biblioteca 'rich'. Instale-a com `pip install rich`.",
                file=sys.stderr,
            )
            sys.exit(1)
        console = Console()

        if requests is None:
            console.print(
                "[yellow]Aviso: instale 'requests' para obter a localização (country) das proxys.[/]"
            )

        entries = perform_health_checks(outbounds, console=console)

        console.print()
        console.rule("Tabela final")
        console.print(render_test_table(entries))

        success = sum(1 for entry in entries if entry.get("status") == "OK")
        fail = len(entries) - success

        console.print()
        console.rule("Resumo do Teste")
        console.print(
            f"[bold cyan]Total:[/] {len(entries)}    "
            f"[bold green]Sucesso:[/] {success}    "
            f"[bold red]Falhas:[/] {fail}"
        )

        failed_entries = [entry for entry in entries if entry.get("error")]
        if failed_entries:
            console.print()
            console.print("[bold red]Detalhes das falhas:[/]")
            for entry in failed_entries:
                console.print(f" - [bold]{entry.get('tag') or '-'}[/]: {entry['error']}")

        sys.exit(0 if success else 1)

    if args.country and not args.verify:
        print("A opção --country só pode ser usada junto com --verify.", file=sys.stderr)
        sys.exit(2)

    approved_outbounds = outbounds
    verify_console = None
    if args.verify:
        if not rich_available:
            print(
                "A opção --verify requer a biblioteca 'rich'. Instale-a com `pip install rich`.",
                file=sys.stderr,
            )
            sys.exit(1)

        verify_console = Console()

        if requests is None:
            verify_console.print(
                "[yellow]Aviso: instale 'requests' para obter a localização (country) das proxys.[/]"
            )
            if args.country:
                verify_console.print(
                    "[red]Não será possível filtrar por país sem 'requests'.[/]",
                    highlight=False,
                )

        entries = perform_health_checks(outbounds, console=verify_console)

        verify_console.print()
        verify_console.rule("Tabela final")
        verify_console.print(render_test_table(entries))

        success = sum(1 for entry in entries if entry.get("status") == "OK")
        fail = len(entries) - success

        verify_console.print()
        verify_console.rule("Resumo do Teste")
        verify_console.print(
            f"[bold cyan]Total:[/] {len(entries)}    "
            f"[bold green]Sucesso:[/] {success}    "
            f"[bold red]Falhas:[/] {fail}"
        )

        failed_entries = [entry for entry in entries if entry.get("error")]
        if failed_entries:
            verify_console.print()
            verify_console.print("[bold red]Detalhes das falhas:[/]")
            for entry in failed_entries:
                verify_console.print(f" - [bold]{entry.get('tag') or '-'}[/]: {entry['error']}")

        selected_entries = [entry for entry in entries if entry.get("status") == "OK"]

        def matches_country(entry: Dict[str, Any], desired: str) -> bool:
            if not desired:
                return True
            desired_norm = desired.strip().casefold()
            if not desired_norm:
                return True
            candidates = []
            for key in ("country", "country_code", "country_name"):
                value = entry.get(key)
                if not value:
                    continue
                candidates.append(str(value).strip())
            for value in candidates:
                norm = value.casefold()
                if norm == desired_norm:
                    return True
            for value in candidates:
                norm = value.casefold()
                if norm and (desired_norm in norm or norm in desired_norm):
                    return True
            return False

        if args.country:
            selected_entries = [entry for entry in selected_entries if matches_country(entry, args.country)]

        if not selected_entries:
            verify_console.print()
            if args.country:
                verify_console.print(
                    f"[red]Nenhuma proxy aprovada corresponde ao país '{args.country}'.[/]",
                    highlight=False,
                )
            else:
                verify_console.print("[red]Nenhuma proxy foi aprovada no teste.[/]")
            sys.exit(1)

        selected_indices = [entry["index"] for entry in selected_entries]
        approved_outbounds = [outbounds[idx] for idx in selected_indices]

        verify_console.print()
        verify_console.rule("Pontes aprovadas")
        for entry in selected_entries:
            destino_preview = format_destination(entry.get("host"), entry.get("port"))
            ping_preview = entry.get("ping")
            ping_fmt = f"{ping_preview:.1f} ms" if isinstance(ping_preview, (int, float)) else "-"
            verify_console.print(
                f"[bold]{entry['tag']}[/] -> {destino_preview} | IP: {entry.get('ip') or '-'} | "
                f"País: {entry.get('country') or '-'} | Ping: {ping_fmt}"
            )

        outbounds = approved_outbounds

    xray_bin = which_xray()

    procs: List[subprocess.Popen] = []
    cfg_paths: List[Path] = []
    bridges: List[Tuple[str, int, str]] = []  # (tag, port, esquema)

    def cleanup(signum=None, frame=None):
        print("\nEncerrando pontes...", file=sys.stderr)
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        # espera um pouco e mata forçado se preciso
        t0 = time.time()
        for p in procs:
            try:
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, cleanup)

    port = args.base_port
    for raw, ob in outbounds:
        cfg = make_xray_config_http_inbound(port, ob)
        proc, cfgp = launch_bridge(xray_bin, cfg, ob.tag)
        procs.append(proc)
        cfg_paths.append(cfgp)
        scheme = raw.split("://", 1)[0].lower()
        bridges.append((ob.tag, port, scheme))
        port += 1

    # Banner
    print("\n=== Pontes HTTP ativas (use como proxy HTTP em cada profile) ===")
    for tag, prt, scheme in bridges:
        print(f"[{scheme:6}] http://127.0.0.1:{prt}  ->  outbound '{tag}'")

    print("\nPressione Ctrl+C para encerrar todas as pontes.\n")
    # Tailing leve do output (útil para debug). Pode ser comentado.
    try:
        while True:
            alive = False
            for p in procs:
                if p.poll() is None:
                    alive = True
                # drena logs (não bloqueante pois stdout=PIPE+text+bufsize=1)
                if p.stdout:
                    line = p.stdout.readline()
                    if line:
                        # Mostra apenas linhas de aviso/erro
                        if "warning" in line.lower() or "error" in line.lower():
                            print(line.rstrip())
            if not alive:
                print("Todos os processos xray finalizaram.")
                break
            time.sleep(0.2)
    finally:
        cleanup()

if __name__ == "__main__":
    main()
