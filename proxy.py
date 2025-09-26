#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cria "pontes" HTTP locais (127.0.0.1:PORTA) para links v2ray/shadowsocks (ss://, vmess://, vless://, trojan://),
usando o Xray-core como cliente. Útil para automação que só aceita proxy HTTP.
Autor: você + ChatGPT :)

Uso básico:
  python bridges_v2ray_http.py --source proxies.txt --base-port 54000
  python bridges_v2ray_http.py --source https://meuservidor.com/minhas-proxys.txt
  cat proxies.txt | python bridges_v2ray_http.py

Cada linha do texto deve conter um link de proxy (ex: ss://..., vmess://..., vless://..., trojan://...).
Linhas vazias ou começando com // ou # são ignoradas.
"""

import argparse
import base64
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs, unquote, quote, urlsplit

try:
    import requests  # opcional: apenas se --source for URL
except Exception:
    requests = None

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

def read_source_text(source: Optional[str]) -> str:
    if source is None:
        # lê da stdin
        return sys.stdin.read()
    if re.match(r"^https?://", source, re.I):
        if requests is None:
            raise RuntimeError("O pacote requests não está instalado. `pip install requests`")
        r = requests.get(source, timeout=30)
        r.raise_for_status()
        return r.text
    # arquivo local
    p = Path(source)
    return p.read_text(encoding="utf-8")

def sanitize_tag(tag: Optional[str], fallback: str) -> str:
    if not tag:
        return fallback
    # remove caracteres problemáticos do nome
    tag = re.sub(r"[^\w\-\.]+", "_", tag)
    return tag[:48] or fallback

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

    # Se contém '@', normalmente é formato (a)
    if '@' in payload:
        creds_b64, rest = payload.split('@', 1)
        creds = b64decode_padded(creds_b64.split('#')[0]).decode('utf-8')
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
        b = b64decode_padded(payload.split('#')[0]).decode('utf-8')
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
    data = json.loads(b64decode_padded(b64).decode("utf-8"))
    tag = sanitize_tag(data.get("ps"), "vmess")
    host = data.get("add")
    port = int(data.get("port", 0))
    uuid = data.get("id")
    alter_id = int(data.get("aid", 0))
    net = (data.get("net") or "tcp").lower()
    tls = (data.get("tls") or "").lower() == "tls"
    sni = data.get("sni") or data.get("host")  # alguns encodem sni em host
    path = data.get("path") or "/"
    host_header = data.get("host")

    if not host or not port or not uuid:
        raise ValueError("vmess:// incompleto (host/port/id).")

    ws_settings = None
    grpc_settings = None
    transport = {}

    if net == "ws":
        ws_settings = {
            "path": path or "/",
            "headers": {"Host": host_header} if host_header else {}
        }
        transport = {"network": "ws", "wsSettings": ws_settings}
    elif net == "grpc":
        service_name = (path or "/").lstrip("/")
        grpc_settings = {"serviceName": service_name}
        transport = {"network": "grpc", "grpcSettings": grpc_settings}
    else:
        transport = {"network": "tcp"}

    security = "tls" if tls else "none"

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
                    "security": "auto"
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
