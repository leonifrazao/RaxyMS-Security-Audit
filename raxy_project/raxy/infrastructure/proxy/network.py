# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import ipaddress
import logging
import re
import socket
import time
from typing import Any, Dict, Optional, Tuple, Iterable

try:
    import requests
except ImportError:
    requests = None

from raxy.interfaces.services.IProxyComponents import IProxyNetworkManager, IProxyProcessManager
from raxy.models.proxy import Outbound
from .parser import decode_bytes

logger = logging.getLogger(__name__)


class NetworkManager(IProxyNetworkManager):
    def __init__(self, requests_session: Any, process_manager: IProxyProcessManager) -> None:
        self.requests = requests_session or requests
        self.process = process_manager

    @staticmethod
    def is_github_api_url(url: str) -> bool:
        """Verifica se a URL é do GitHub API."""
        return bool(re.match(r"^https://api\.github\.com/repos/.+/contents/.+", url, re.I))

    @staticmethod
    def is_github_raw_url(url: str) -> bool:
        """Verifica se a URL é do GitHub raw content."""
        return bool(re.match(r"^https://raw\.githubusercontent\.com/.+", url, re.I))

    @staticmethod
    def convert_raw_to_api_url(raw_url: str) -> str:
        """Converte uma URL raw do GitHub para a URL da API."""
        match = re.match(
            r"^https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$",
            raw_url,
            re.I
        )
        
        if not match:
            logger.warning(f"URL raw do GitHub não reconhecida: {raw_url}")
            return raw_url
        
        owner, repo, ref, path = match.groups()
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
        logger.info(f"URL convertida de raw para API: {api_url}")
        return api_url

    @staticmethod
    def decode_github_api_content(api_response: Dict[str, Any]) -> str:
        if not isinstance(api_response, dict):
            raise ValueError("Resposta da API deve ser um dicionário")
        
        content_b64 = api_response.get("content")
        if not content_b64:
            raise ValueError("Campo 'content' não encontrado na resposta da API")
        
        encoding = api_response.get("encoding", "base64")
        if encoding != "base64":
            logger.warning(f"Encoding inesperado na resposta da API: {encoding}")
        
        try:
            cleaned_content = content_b64.replace("\n", "").replace("\r", "").strip()
            decoded_bytes = base64.b64decode(cleaned_content)
            decoded_text = decoded_bytes.decode("utf-8")
            logger.debug(f"Conteúdo decodificado com sucesso: {len(decoded_text)} caracteres")
            return decoded_text
        except base64.binascii.Error as exc:
            logger.error(f"Erro ao decodificar base64: {exc}")
            raise ValueError(f"Conteúdo base64 inválido: {exc}") from exc
        except UnicodeDecodeError as exc:
            logger.error(f"Erro ao decodificar UTF-8: {exc}")
            try:
                decoded_text = decoded_bytes.decode("latin-1")
                logger.warning("Conteúdo decodificado usando latin-1 como fallback")
                return decoded_text
            except Exception:
                raise exc

    @staticmethod
    def validate_proxies(proxy_text: str) -> Tuple[bool, int, str]:
        if not proxy_text or not proxy_text.strip():
            logger.warning("Texto de proxy vazio ou inválido")
            return (False, 0, "Nenhum conteúdo de proxy encontrado")
        
        lines = proxy_text.strip().splitlines()
        valid_schemes = ("ss://", "vmess://", "vless://", "trojan://")
        valid_count = 0
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if any(line.lower().startswith(scheme) for scheme in valid_schemes):
                valid_count += 1
        
        if valid_count == 0:
            logger.warning("Nenhuma proxy válida encontrada no conteúdo")
            return (False, 0, "Nenhuma proxy válida encontrada (esquemas suportados: ss, vmess, vless, trojan)")
        
        logger.info(f"{valid_count} proxies válidas encontradas no conteúdo")
        return (True, valid_count, f"{valid_count} proxy(ies) válida(s) encontrada(s)")

    def fetch_github_api_content(self, api_url: str) -> str:
        logger.info(f"Buscando conteúdo da API do GitHub: {api_url}")
        try:
            resp = self.requests.get(
                api_url,
                timeout=30,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Raxy-Proxy-Manager/1.0"
                }
            )
            
            remaining = resp.headers.get("X-RateLimit-Remaining", "unknown")
            limit = resp.headers.get("X-RateLimit-Limit", "unknown")
            logger.debug(f"GitHub API rate limit: {remaining}/{limit}")
            
            if resp.status_code == 403:
                reset_time = resp.headers.get("X-RateLimit-Reset")
                if reset_time:
                    from datetime import datetime
                    reset_dt = datetime.fromtimestamp(int(reset_time))
                    error_msg = f"Rate limit da API do GitHub excedido. Limite será resetado em: {reset_dt.strftime('%Y-%m-%d %H:%M:%S')}"
                else:
                    error_msg = "Rate limit da API do GitHub excedido"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            if resp.status_code == 404:
                logger.error(f"Recurso não encontrado na API do GitHub: {api_url}")
                raise RuntimeError(f"Recurso não encontrado na API do GitHub: {api_url}")
            
            resp.raise_for_status()
            
            try:
                api_response = resp.json()
            except json.JSONDecodeError as exc:
                logger.error(f"Resposta da API do GitHub não é JSON válido: {exc}")
                raise ValueError(f"Resposta da API do GitHub inválida: {exc}") from exc
            
            decoded_content = self.decode_github_api_content(api_response)
            
            has_valid, count, message = self.validate_proxies(decoded_content)
            if not has_valid:
                logger.warning(f"Aviso: {message}")
            else:
                logger.info(f"Sucesso: {message}")
            
            return decoded_content
            
        except self.requests.exceptions.Timeout:
            logger.error(f"Timeout ao acessar API do GitHub: {api_url}")
            raise RuntimeError(f"Timeout ao acessar API do GitHub (timeout=30s)")
        except self.requests.exceptions.ConnectionError as exc:
            logger.error(f"Erro de conexão ao acessar API do GitHub: {exc}")
            raise RuntimeError(f"Erro de conexão ao acessar API do GitHub") from exc
        except self.requests.exceptions.RequestException as exc:
            logger.error(f"Erro na requisição à API do GitHub: {exc}")
            raise RuntimeError(f"Erro ao acessar API do GitHub: {exc}") from exc

    def read_source_text(self, source: str) -> str:
        if not re.match(r"^https?://", source, re.I):
            logger.info(f"Lendo arquivo local: {source}")
            # Import path here or expect it passed? 
            # Original code: path = Path(source)
            from pathlib import Path
            path = Path(source)
            return decode_bytes(path.read_bytes())
        
        if self.requests is None:
            raise RuntimeError(
                "O pacote requests não está disponível para baixar URLs de proxy. "
                "Instale com: pip install requests"
            )
        
        # Tenta usar a API do GitHub se for uma URL raw ou API
        # Isso evita rate limits de IP direto no raw.githubusercontent e permite auth se configurado
        is_raw = self.is_github_raw_url(source)
        is_api = self.is_github_api_url(source)
        
        if is_raw or is_api:
            api_url = source
            if is_raw:
                logger.info(f"URL raw do GitHub detectada, tentando buscar via API: {source}")
                api_url = self.convert_raw_to_api_url(source)
            
            try:
                return self.fetch_github_api_content(api_url)
            except Exception as e:
                logger.warning(f"Erro ao buscar via API do GitHub: {e}")
                if is_raw:
                    logger.info(f"Ativando fallback: baixando diretamente da URL raw: {source}")
                    # Continua para o download genérico abaixo com a URL source original
                else:
                    # Se era API pura e falhou, relança, pois não temos uma URL raw de fallback
                    # A menos que queiramos baixar o JSON da API como texto, o que não ajuda muito em proxies
                    raise e
        
        logger.info(f"Baixando conteúdo de URL genérica: {source}")
        try:
            resp = self.requests.get(source, timeout=30)
            resp.raise_for_status()
            return decode_bytes(resp.content, encoding_hint=resp.encoding or None)
        except self.requests.exceptions.Timeout:
            logger.error(f"Timeout ao acessar {source}")
            raise RuntimeError(f"Timeout ao acessar {source} (timeout=30s)")
        except self.requests.exceptions.ConnectionError as exc:
            logger.error(f"Erro de conexão ao acessar {source}: {exc}")
            raise RuntimeError(f"Erro de conexão ao acessar {source}") from exc

    @staticmethod
    def is_public_ip(ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return not (
            addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast or addr.is_link_local
        )

    def lookup_country(self, ip: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
        if not ip or self.requests is None or not self.is_public_ip(ip):
            return None
        try:
            token = "747e7c8d93c344d2973066cf6eeb7d93"
            resp = self.requests.get(
                f"https://api.findip.net/{ip}/?token={token}", 
                timeout=5
            )
            resp.raise_for_status()
            data = resp.json()
            
            country_info = data.get("country", {})
            country_code = country_info.get("iso_code")
            if isinstance(country_code, str):
                country_code = (country_code.strip() or None)
                if country_code:
                    country_code = country_code.upper()
            
            country_names = country_info.get("names", {})
            country_name = country_names.get("en")
            
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

    def outbound_host_port(self, outbound: Outbound) -> Tuple[str, int]:
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

    def test_outbound(self, raw_uri: str, outbound: Outbound, timeout: float = 10.0) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "tag": outbound.tag,
            "protocol": outbound.config.get("protocol"),
            "uri": raw_uri,
        }
        
        try:
            host, port = self.outbound_host_port(outbound)
        except Exception as exc:
            result["error"] = f"host/port não identificados: {exc}"
            return result

        result["host"] = host
        result["port"] = port

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

        if result.get("ip"):
            country_info = self.lookup_country(result["ip"])
            if country_info:
                if label := country_info.get("label"):
                    result["country"] = label
                if code := country_info.get("code"):
                    result["country_code"] = code
                if name := country_info.get("name"):
                    result["country_name"] = name

        func_result = self.test_proxy_functionality(
            raw_uri, outbound, timeout=timeout
        )
        
        if func_result.get("functional"):
            result["ping_ms"] = func_result.get("response_time")
            result["functional"] = True
            result["external_ip"] = func_result.get("external_ip")
            
            if func_result.get("external_ip") and func_result["external_ip"] != result.get("ip"):
                result["proxy_ip"] = func_result["external_ip"]
                proxy_country = self.lookup_country(func_result["external_ip"])
                if proxy_country:
                    result["proxy_country"] = proxy_country.get("label")
                    result["proxy_country_code"] = proxy_country.get("code")
        else:
            result["error"] = func_result.get("error", "Proxy não funcional")
            result["functional"] = False

        return result

    def test_proxy_functionality(
        self, 
        raw_uri: str, 
        outbound: Outbound,
        timeout: float = 10.0,
        test_url: str = "http://httpbin.org/ip"
    ) -> Dict[str, Any]:
        result = {
            "functional": False,
            "response_time": None,
            "external_ip": None,
            "error": None
        }
        
        if self.requests is None:
            result["error"] = "requests não disponível para teste funcional"
            return result
        
        exceptions_mod = getattr(self.requests, "exceptions", None)
        if exceptions_mod is None and requests is not None:
            exceptions_mod = getattr(requests, "exceptions", None)

        response = None
        duration_ms: Optional[float] = None

        try:
            with self.process.temporary_bridge(outbound, tag_prefix="test") as (test_port, _):
                proxy_url = f"http://127.0.0.1:{test_port}"
                proxies = {"http": proxy_url, "https": proxy_url}
                start_time = time.perf_counter()
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }

                response = self.requests.get(
                    test_url,
                    proxies=proxies,
                    timeout=timeout,
                    verify=False,
                    headers=headers
                )
                response.raise_for_status()
                duration_ms = (time.perf_counter() - start_time) * 1000
        except RuntimeError as exc:
            result["error"] = str(exc)
            return result
        except Exception as exc:
            result["error"] = self.format_request_error(exc, timeout, exceptions_mod)
            return result

        result["functional"] = True
        result["response_time"] = duration_ms
        if response is not None:
            result["external_ip"] = self.extract_external_ip(response)
        return result

    @staticmethod
    def matches_exception(exc: Exception, candidate: Any) -> bool:
        if candidate is None:
            return False
        try:
            return isinstance(exc, candidate)
        except TypeError:
            return False

    def format_request_error(self, exc: Exception, timeout: float, exceptions_mod: Any) -> str:
        timeout_exc = getattr(exceptions_mod, "Timeout", None) if exceptions_mod else None
        proxy_exc = getattr(exceptions_mod, "ProxyError", None) if exceptions_mod else None
        conn_exc = getattr(exceptions_mod, "ConnectionError", None) if exceptions_mod else None
        http_exc = getattr(exceptions_mod, "HTTPError", None) if exceptions_mod else None

        if self.matches_exception(exc, timeout_exc):
            return f"Timeout após {timeout:.1f}s"
        if self.matches_exception(exc, proxy_exc):
            return f"Erro de proxy: {str(exc)[:100]}"
        if self.matches_exception(exc, conn_exc):
            return f"Erro de conexão: {str(exc)[:100]}"
        if self.matches_exception(exc, http_exc):
            response = getattr(exc, 'response', None)
            if response is not None:
                return f"Erro HTTP {response.status_code}: {response.reason}"
        
        return f"Erro na requisição: {str(exc)[:100]}"

    @staticmethod
    def extract_external_ip(response: Any) -> Optional[str]:
        try:
            data = response.json()
        except Exception:
            return None

        origin = data.get("origin")
        if isinstance(origin, str) and origin.strip():
            return origin.split(",")[0].strip()

        return None
