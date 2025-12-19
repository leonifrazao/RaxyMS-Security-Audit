# -*- coding: utf-8 -*-
"""
Parser de URIs de proxy para V2Ray/Xray.

Suporta os protocolos:
- Shadowsocks (ss://)
- VMess (vmess://)
- VLESS (vless://)
- Trojan (trojan://)

Cada parser converte uma URI em um dicionário de configuração
compatível com o formato Xray/V2Ray.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse, urlsplit

from raxy.infrastructure.proxy.models import Outbound
from raxy.infrastructure.proxy.utils import b64decode_padded, decode_bytes, sanitize_tag


class ProxyURIParser:
    """
    Parser de URIs de proxy V2Ray/Xray.
    
    Converte URIs nos formatos ss://, vmess://, vless://, trojan://
    para configurações de outbound do Xray.
    
    Example:
        >>> parser = ProxyURIParser()
        >>> outbound = parser.parse("vmess://eyJhZGQiOiIxLjIuMy40IiwicG9ydCI6NDQzLi4ufQ==")
        >>> outbound.tag
        'vmess_server'
    """
    
    # Esquemas suportados mapeados para seus parsers
    SUPPORTED_SCHEMES = {"ss", "vmess", "vless", "trojan"}
    
    def parse(self, uri: str) -> Outbound:
        """
        Direciona o link para o parser adequado de acordo com o esquema.
        
        Args:
            uri: URI do proxy no formato scheme://...
            
        Returns:
            Outbound configurado para o Xray
            
        Raises:
            ValueError: Se o esquema não for suportado ou URI inválida
        """
        uri = uri.strip()
        if not uri or uri.startswith("#") or uri.startswith("//"):
            raise ValueError("Linha vazia ou comentário.")
        
        match = re.match(r"^([a-z0-9]+)://", uri, re.I)
        if not match:
            raise ValueError(f"Esquema desconhecido na linha: {uri[:80]}")
        
        scheme = match.group(1).lower()
        
        parser_method = {
            "ss": self._parse_ss,
            "vmess": self._parse_vmess,
            "vless": self._parse_vless,
            "trojan": self._parse_trojan,
        }.get(scheme)
        
        if parser_method is None:
            raise ValueError(f"Esquema não suportado: {scheme}")
        
        return parser_method(uri)
    
    def _parse_ss(self, uri: str) -> Outbound:
        """
        Normaliza um link ss:// incluindo casos em JSON inline.
        
        Suporta dois formatos:
        1. ss://base64(json_config)#tag
        2. ss://base64(method:password)@host:port#tag
        
        Args:
            uri: URI Shadowsocks
            
        Returns:
            Outbound configurado
        """
        frag = urlsplit(uri).fragment
        tag = sanitize_tag(unquote(frag) if frag else None, "ss")

        payload = uri.strip()[5:]  # Remove 'ss://'
        stripped_payload = payload.split('#')[0]

        # Tenta decodificar como JSON inline
        outbound = self._try_parse_ss_json(stripped_payload, tag)
        if outbound:
            return outbound

        # Parse formato padrão: method:password@host:port
        return self._parse_ss_standard(stripped_payload, tag)
    
    def _try_parse_ss_json(self, payload: str, tag: str) -> Optional[Outbound]:
        """
        Tenta fazer parse de SS no formato JSON inline.
        
        Args:
            payload: Payload base64 (sem fragment)
            tag: Tag para o outbound
            
        Returns:
            Outbound se for JSON válido, None caso contrário
        """
        try:
            decoded_preview = decode_bytes(b64decode_padded(payload))
        except Exception:
            return None

        text_preview = decoded_preview.strip()
        if not (text_preview.startswith('{') and text_preview.endswith('}')):
            return None
        
        try:
            data_json = json.loads(text_preview)
        except json.JSONDecodeError:
            return None
        
        # Verifica se tem campos necessários para SS
        required_keys = {"server", "method"}, {"address", "method"}, {"server", "password"}
        if not any(keys.issubset(data_json.keys()) for keys in required_keys):
            return None
        
        ss_host = data_json.get("server") or data_json.get("address")
        ss_port_raw = data_json.get("server_port") or data_json.get("port")
        ss_method = data_json.get("method") or data_json.get("cipher")
        ss_password = data_json.get("password") or data_json.get("passwd") or ""
        
        if not ss_host or not ss_port_raw or not ss_method:
            raise ValueError("Link ss:// incompleto (server/port/method ausentes no JSON).")
        
        try:
            ss_port = int(str(ss_port_raw).strip())
        except (TypeError, ValueError) as e:
            raise ValueError(f"Porta ss inválida: {ss_port_raw!r}") from e
        
        return Outbound(tag, {
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
    
    def _parse_ss_standard(self, payload: str, tag: str) -> Outbound:
        """
        Parse SS no formato padrão base64(method:password)@host:port.
        
        Args:
            payload: Payload sem fragment
            tag: Tag para o outbound
            
        Returns:
            Outbound configurado
        """
        at_split = payload.rsplit('@', 1)
        if len(at_split) != 2:
            raise ValueError("Formato ss:// inválido.")
        
        userinfo_b64, hostport = at_split
        
        try:
            userinfo = decode_bytes(b64decode_padded(userinfo_b64))
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

        return Outbound(tag, {
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
        })
    
    def _parse_vmess(self, uri: str) -> Outbound:
        """
        Converte links vmess:// com conteúdo base64 para outbounds.
        
        Args:
            uri: URI VMess (vmess://base64_json)
            
        Returns:
            Outbound configurado
        """
        payload = uri.strip()[8:]  # Remove 'vmess://'
        
        try:
            decoded = decode_bytes(b64decode_padded(payload))
        except Exception as exc:
            raise ValueError(f"Erro ao decodificar vmess://: {exc}") from exc
        
        try:
            data = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON inválido em vmess://: {exc}") from exc
        
        return self._vmess_outbound_from_dict(data)
    
    def _vmess_outbound_from_dict(
        self, 
        data: Dict[str, Any], 
        *, 
        tag_fallback: str = "vmess"
    ) -> Outbound:
        """
        Adapta o dicionário decodificado de vmess para a estrutura do Xray.
        
        Args:
            data: Dicionário com configuração VMess
            tag_fallback: Tag padrão se não especificada
            
        Returns:
            Outbound configurado
        """
        tag = sanitize_tag(data.get("ps"), tag_fallback)

        host = data.get("add") or data.get("address")
        port_raw = data.get("port", 0)
        
        try:
            port = int(str(port_raw).strip())
        except (TypeError, ValueError) as e:
            raise ValueError(f"Porta vmess inválida: {port_raw!r}") from e

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

        transport = self._build_transport_settings(net, path, host_header, data)
        scy = data.get("scy") or "auto"

        outbound_config: Dict[str, Any] = {
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

        return Outbound(tag, outbound_config)
    
    def _build_transport_settings(
        self,
        net: str,
        path: str,
        host_header: Optional[str],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Constrói configurações de transporte baseadas no tipo de rede.
        
        Args:
            net: Tipo de rede (tcp, ws, grpc)
            path: Caminho para WebSocket
            host_header: Header Host para WS
            data: Dados originais (para serviceName do gRPC)
            
        Returns:
            Dict com configurações de transporte
        """
        if net == "ws":
            return {
                "network": "ws",
                "wsSettings": {
                    "path": path or "/",
                    "headers": {"Host": host_header} if host_header else {}
                }
            }
        elif net == "grpc":
            service_name = data.get("serviceName") or (path or "/").lstrip("/")
            return {
                "network": "grpc",
                "grpcSettings": {"serviceName": service_name}
            }
        else:
            return {"network": "tcp"}
    
    def _parse_vless(self, uri: str) -> Outbound:
        """
        Converte links vless:// adicionando suporte a transportes modernos.
        
        Args:
            uri: URI VLESS
            
        Returns:
            Outbound configurado
        """
        p = urlparse(uri)
        tag = sanitize_tag(unquote(p.fragment) if p.fragment else None, "vless")
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

        transport = self._build_vless_transport(net, path, host_header, service_name)
        stream = self._build_stream_settings(security, sni, alpn, transport)

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
        return Outbound(tag, outbound)
    
    def _build_vless_transport(
        self,
        net: str,
        path: str,
        host_header: Optional[str],
        service_name: str
    ) -> Dict[str, Any]:
        """
        Constrói transporte para VLESS.
        
        Args:
            net: Tipo de rede
            path: Path WS
            host_header: Host header
            service_name: Nome do serviço gRPC
            
        Returns:
            Dict de configuração de transporte
        """
        if net == "ws":
            return {
                "network": "ws", 
                "wsSettings": {
                    "path": path,
                    "headers": {"Host": host_header} if host_header else {}
                }
            }
        elif net == "grpc":
            return {"network": "grpc", "grpcSettings": {"serviceName": service_name}}
        else:
            return {"network": "tcp"}
    
    def _build_stream_settings(
        self,
        security: str,
        sni: Optional[str],
        alpn: list[str],
        transport: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Constrói configurações de stream com TLS/Reality.
        
        Args:
            security: Tipo de segurança (none, tls, reality)
            sni: Server Name Indication
            alpn: Application-Layer Protocol Negotiation
            transport: Configurações de transporte
            
        Returns:
            Dict com configurações de stream
        """
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
        
        return stream
    
    def _parse_trojan(self, uri: str) -> Outbound:
        """
        Converte links trojan:// assegurando parâmetros TLS e transporte.
        
        Args:
            uri: URI Trojan
            
        Returns:
            Outbound configurado
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

        transport = self._build_vless_transport(net, path, host_header, service_name)
        stream = self._build_stream_settings(security, sni, alpn, transport)

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


# Instância singleton para uso conveniente
_parser = ProxyURIParser()
parse_proxy_uri = _parser.parse


__all__ = ["ProxyURIParser", "parse_proxy_uri"]
