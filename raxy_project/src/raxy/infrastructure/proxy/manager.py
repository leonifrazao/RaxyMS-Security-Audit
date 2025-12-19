# -*- coding: utf-8 -*-
"""
Gerenciador principal de proxies V2Ray/Xray.

O módulo expõe a classe ProxyManager que gerencia:
- Carregamento de links de proxy
- Testes com filtragem opcional por país
- Criação de túneis HTTP locais com Xray

Este módulo é a interface pública do pacote de proxy. Para detalhes
de implementação, veja os módulos internos: parser, cache, bridge, etc.
"""

from __future__ import annotations

import random
import re
import socket
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from raxy.infrastructure.logging import get_logger, debug_log
from raxy.infrastructure.proxy.models import Outbound, BridgeRuntime
from raxy.infrastructure.proxy.parser import ProxyURIParser
from raxy.infrastructure.proxy.cache import ProxyCacheManager
from raxy.infrastructure.proxy.display import ProxyDisplayManager
from raxy.infrastructure.proxy.bridge import XrayBridgeManager
from raxy.infrastructure.proxy.utils import (
    decode_bytes,
    format_timestamp,
    is_public_ip,
    safe_float,
    safe_int,
)

# Imports opcionais
try:
    import requests as requests_module
except ImportError:
    requests_module = None  # type: ignore

__all__ = ["ProxyManager"]

logger = get_logger()


class ProxyManager:
    """
    Gerencia uma coleção de proxies V2Ray/Xray.
    
    Responsabilidades:
    - Carregar proxies de URIs ou fontes remotas
    - Testar conectividade real via pontes temporárias
    - Criar pontes HTTP locais para uso
    - Gerenciar cache de resultados
    
    Attributes:
        country_filter: Filtro de país para proxies
        entries: Lista de proxies carregadas com status
        
    Example:
        >>> manager = ProxyManager(sources=["https://example.com/proxies.txt"])
        >>> manager.test(threads=10, country="US")
        >>> proxies = manager.start(amounts=5)
        >>> print(proxies[0]["url"])  # http://127.0.0.1:54321
        >>> manager.stop()
    
    Note:
        Para backward compatibility, a classe mantém dataclasses Outbound
        e BridgeRuntime como atributos de classe.
    """

    # Backward compatibility - expõe classes internas
    Outbound = Outbound
    BridgeRuntime = BridgeRuntime
    
    # Constantes de cache
    DEFAULT_CACHE_FILENAME: str = "proxy_cache.json"
    CACHE_VERSION: int = 1

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
        cache_path: Optional[Union[str, Path]] = None,
        command_output: bool = True,
        requests_session: Optional[Any] = None,
    ) -> None:
        """
        Inicializa o gerenciador de proxies.
        
        Args:
            proxies: Lista de URIs de proxy para carregar
            sources: Fontes (arquivos ou URLs) contendo proxies
            country: Código do país para filtrar (ex: "US", "BR")
            base_port: Porta base para alocação (deprecated)
            max_count: Limite de proxies a carregar (0 = sem limite)
            use_console: Se deve usar Rich para exibição
            use_cache: Se deve usar cache de testes
            cache_path: Caminho customizado para cache
            command_output: Se deve mostrar output de comandos
            requests_session: Sessão requests customizada
        """
        # Configurações
        self.country_filter = country
        self.base_port = base_port
        self.max_count = max_count
        self.command_output = command_output
        
        # Módulo requests
        self.requests = requests_session or requests_module
        
        # Inicializa componentes
        self._parser = ProxyURIParser()
        self._cache = ProxyCacheManager(
            cache_path=Path(cache_path) if cache_path else None,
            enabled=use_cache,
        )
        self._display = ProxyDisplayManager(enabled=use_console)
        self._bridge_manager = XrayBridgeManager()
        
        # Estado interno
        self._outbounds: List[Tuple[str, Outbound]] = []
        self._entries: List[Dict[str, Any]] = []
        self._parse_errors: List[str] = []
        
        # Carrega cache se habilitado
        if use_cache:
            self._cache.load()
        
        # Carrega proxies iniciais
        if proxies:
            self.add_proxies(proxies)
        if sources:
            self.add_sources(sources)
        
        # Reconstrói entries do cache se necessário
        if use_cache and not self._entries and self._outbounds:
            self._prime_entries_from_cache()

    # =========================================================================
    # Propriedades públicas
    # =========================================================================
    
    @property
    def entries(self) -> List[Dict[str, Any]]:
        """Retorna os registros carregados ou decorrentes dos últimos testes."""
        return self._entries
    
    @property
    def parse_errors(self) -> List[str]:
        """Lista de linhas ignoradas ao interpretar os links informados."""
        return list(self._parse_errors)
    
    @property
    def console(self) -> Optional[Any]:
        """Console Rich (para compatibilidade)."""
        return self._display.console
    
    @property
    def use_console(self) -> bool:
        """Se exibição Rich está ativada."""
        return self._display.enabled
    
    @property
    def use_cache(self) -> bool:
        """Se cache está habilitado."""
        return self._cache.enabled
    
    @property
    def _running(self) -> bool:
        """Se há pontes em execução."""
        return self._bridge_manager.is_running
    
    @property
    def _bridges(self) -> List[BridgeRuntime]:
        """Lista de pontes ativas."""
        return self._bridge_manager.bridges

    # =========================================================================
    # Carregamento de proxies
    # =========================================================================
    
    def add_proxies(self, proxies: Iterable[str]) -> int:
        """
        Adiciona proxies a partir de URIs.
        
        Suporta esquemas: ss://, vmess://, vless://, trojan://
        
        Args:
            proxies: Iterable de URIs de proxy
            
        Returns:
            Quantidade de proxies adicionadas com sucesso
        """
        added = 0
        for raw in proxies:
            if raw is None:
                continue
            
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            
            try:
                outbound = self._parser.parse(line)
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
        """
        Carrega proxies de arquivos ou URLs.
        
        Args:
            sources: Lista de caminhos de arquivo ou URLs
            
        Returns:
            Quantidade total de proxies adicionadas
        """
        added = 0
        for src in sources:
            text = self._read_source_text(src)
            lines = [ln.strip() for ln in text.splitlines()]
            added += self.add_proxies(lines)
        return added

    # =========================================================================
    # Testes de proxy
    # =========================================================================
    
    def test(
        self,
        *,
        threads: int = 1,
        country: Optional[str] = None,
        verbose: Optional[bool] = None,
        timeout: float = 10.0,
        force: bool = False,
        find_first: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Testa as proxies carregadas medindo funcionalidade real.
        
        Cria pontes temporárias para cada proxy e faz requisição
        via httpbin.org/ip para validar funcionamento.
        
        Args:
            threads: Número de workers paralelos
            country: Filtro de país (sobrescreve country_filter)
            verbose: Se deve mostrar progresso (None = usa use_console)
            timeout: Timeout para cada teste
            force: Se deve ignorar cache e re-testar tudo
            find_first: Parar após encontrar N proxies funcionais
            
        Returns:
            Lista de dicionários com resultados dos testes
            
        Raises:
            RuntimeError: Se nenhuma proxy foi carregada
        """
        if not self._outbounds:
            raise RuntimeError("Nenhuma proxy carregada para testar.")

        country_filter = country if country is not None else self.country_filter
        emit = self._display if (verbose is None or verbose) else None

        results = self._perform_health_checks(
            self._outbounds,
            country_filter=country_filter,
            emit_progress=emit,
            force_refresh=force,
            functional_timeout=timeout,
            threads=threads,
            stop_on_success=find_first,
        )

        self._entries = results
        self.country_filter = country_filter
        self._cache.save(results)

        if self._display.enabled and (verbose is None or verbose):
            self._display.render_test_summary(results, country_filter)

        return results
    
    @debug_log(log_args=False, log_result=False, log_duration=True)
    def start(
        self,
        *,
        threads: Optional[int] = None,
        amounts: Optional[int] = None,
        country: Optional[str] = None,
        auto_test: bool = True,
        wait: bool = False,
        find_first: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Cria pontes HTTP locais para as proxies aprovadas.
        
        Args:
            threads: Workers para teste (se auto_test=True)
            amounts: Limite de pontes a criar
            country: Filtro de país
            auto_test: Se deve testar antes de iniciar
            wait: Se deve bloquear aguardando Ctrl+C
            find_first: Parar teste após N sucessos
            
        Returns:
            Lista de dicts com {id, url, uri} de cada ponte
            
        Raises:
            RuntimeError: Se já em execução ou sem proxies
        """
        if self._bridge_manager.is_running:
            raise RuntimeError(
                "As pontes já estão em execução. Chame stop() antes de iniciar novamente."
            )
        if not self._outbounds:
            raise RuntimeError("Nenhuma proxy carregada para iniciar.")

        country_filter = country if country is not None else self.country_filter
        
        if auto_test:
            self.test(
                threads=threads or 1,
                country=country_filter,
                verbose=self._display.enabled,
                find_first=find_first
            )
            country_filter = self.country_filter

        # Filtra proxies aprovadas
        approved_entries = [
            entry for entry in self._entries
            if entry.get("status") == "OK" 
            and self.matches_country(entry, country_filter)
        ]
        
        # Ordena por ping
        approved_entries.sort(
            key=lambda e: e.get("ping") if isinstance(e.get("ping"), (int, float)) else float('inf')
        )
        
        if not approved_entries:
            msg = "Nenhuma proxy aprovada para iniciar."
            if country_filter:
                msg = f"Nenhuma proxy aprovada para o país '{country_filter}'."
            raise RuntimeError(msg)

        # Aplica limite
        if amounts is not None:
            if not isinstance(amounts, int) or amounts <= 0:
                raise ValueError("amounts deve ser um inteiro positivo.")
            if amounts < len(approved_entries):
                approved_entries = approved_entries[:amounts]
            elif amounts > len(approved_entries) and self._display.enabled:
                self._display.print(
                    f"Atenção: solicitado amounts={amounts} mas só existem "
                    f"{len(approved_entries)} proxies aprovadas."
                )

        # Prepara outbounds
        outbounds_to_start = [
            (self._outbounds[entry["index"]][0], self._outbounds[entry["index"]][1])
            for entry in approved_entries
        ]

        # Cria pontes
        if self._display.enabled:
            self._display.print("")
            self._display.print(
                f"[green]Iniciando {len(approved_entries)} pontes ordenadas por ping[/]"
            )

        bridges = self._bridge_manager.create_bridges(outbounds_to_start)
        
        # Exibe pontes
        if self._display.enabled:
            bridges_display = [
                (bridge, e.get("ping") or float('inf'))
                for bridge, e in zip(bridges, approved_entries)
            ]
            self._display.show_bridges(bridges_display, country_filter)

        bridges_with_id = [
            {"id": idx, "url": bridge.url, "uri": bridge.uri}
            for idx, bridge in enumerate(bridges)
        ]

        if wait:
            self._bridge_manager.wait(console=self._display.console)
        else:
            self._bridge_manager.start_wait_thread()

        return bridges_with_id
    
    def stop(self) -> None:
        """Finaliza processos Xray ativos e limpa recursos."""
        self._bridge_manager.stop_all()
    
    def wait(self) -> None:
        """Bloqueia até que todas as pontes terminem ou stop seja chamado."""
        self._bridge_manager.wait(console=self._display.console)
    
    def get_http_proxy(self) -> List[Dict[str, Any]]:
        """
        Retorna informações das pontes em execução.
        
        Returns:
            Lista de {id, url, uri} para cada ponte ativa
        """
        if not self._bridge_manager.is_running:
            return []
        return [
            {"id": idx, "url": bridge.url, "uri": bridge.uri}
            for idx, bridge in enumerate(self._bridge_manager.bridges)
        ]
    
    def rotate_proxy(self, bridge_id: int) -> bool:
        """
        Troca a proxy de uma ponte por outra aleatória e funcional.
        
        Args:
            bridge_id: ID da ponte a rotacionar
            
        Returns:
            True se rotacionou com sucesso
        """
        bridges = self._bridge_manager.bridges
        
        if not self._bridge_manager.is_running or not (0 <= bridge_id < len(bridges)):
            if self._display.enabled:
                msg = f"ID de ponte inválido: {bridge_id}. IDs válidos: 0 a {len(bridges) - 1}."
                self._display.print(f"[red]Erro: {msg}[/red]")
            return False

        bridge = bridges[bridge_id]
        uri_to_replace = bridge.uri

        # Invalida a proxy antiga no cache
        entry_to_invalidate = next(
            (e for e in self._entries if e.get("uri") == uri_to_replace), 
            None
        )
        if entry_to_invalidate:
            entry_to_invalidate["status"] = "ERRO"
            entry_to_invalidate["error"] = "Proxy invalidada manualmente via rotação"
            entry_to_invalidate["tested_at_ts"] = time.time()
            self._cache.save(self._entries)
            if self._display.enabled:
                self._display.print(
                    f"[dim]Proxy '{bridge.tag}' marcada como inválida no cache.[/dim]"
                )

        # Encontra candidatas
        candidates = [
            entry for entry in self._entries
            if entry.get("status") == "OK"
            and self.matches_country(entry, self.country_filter)
            and entry.get("uri") != uri_to_replace
        ]

        if not candidates:
            if self._display.enabled:
                self._display.print(
                    f"[yellow]Nenhuma outra proxy disponível para rotacionar.[/yellow]"
                )
            return False

        new_entry = random.choice(candidates)
        new_uri, new_outbound = self._outbounds[new_entry["index"]]

        new_bridge = self._bridge_manager.rotate_bridge(
            bridge_id, new_outbound, new_uri
        )
        
        if new_bridge is None:
            if self._display.enabled:
                self._display.print(
                    f"[red]Falha ao rotacionar ponte {bridge_id}.[/red]"
                )
            return False

        if self._display.enabled:
            self._display.print(
                f"[green]Sucesso:[/green] Ponte [bold]ID {bridge_id}[/] rotacionada "
                f"para '[bold]{new_outbound.tag}[/]'"
            )
        
        return True

    # =========================================================================
    # Métodos de filtro de país
    # =========================================================================
    
    @classmethod
    def matches_country(cls, entry: Dict[str, Any], desired: Optional[str]) -> bool:
        """
        Valida se o registro atende ao filtro de país.
        
        Verifica tanto o país do servidor quanto o país de saída real.
        
        Args:
            entry: Dicionário com dados da proxy
            desired: Código ou nome do país desejado
            
        Returns:
            True se corresponde ao filtro (ou filtro vazio)
        """
        if not desired:
            return True

        exit_country_info = {
            "country": entry.get("proxy_country"),
            "country_code": entry.get("proxy_country_code"),
        }
        server_country_info = {
            "country": entry.get("country"),
            "country_code": entry.get("country_code"),
            "country_name": entry.get("country_name"),
        }

        # Usa exit info se disponível, senão server info
        effective_exit_info = (
            exit_country_info 
            if exit_country_info.get("country") 
            else server_country_info
        )
        
        if not cls._check_country_match(effective_exit_info, desired):
            return False
            
        # Se servidor e saída são diferentes, ambos devem corresponder
        if entry.get("proxy_ip") and entry.get("proxy_ip") != entry.get("ip"):
            if not cls._check_country_match(server_country_info, desired):
                return False
                
        return True
    
    @staticmethod
    def _check_country_match(
        country_info: Dict[str, Any], 
        desired: Optional[str]
    ) -> bool:
        """
        Verifica se informações de país correspondem ao desejado.
        
        Args:
            country_info: Dict com country, country_code, country_name
            desired: País desejado
            
        Returns:
            True se há correspondência
        """
        if not desired:
            return True
        
        desired_norm = desired.strip().casefold()
        if not desired_norm:
            return True

        candidates = [
            str(country_info.get(k) or "").strip()
            for k in ("country", "country_code", "country_name")
            if country_info.get(k)
        ]
        candidates = [c for c in candidates if c and c != "-"]

        if not candidates:
            return False

        for c in candidates:
            if c.casefold() == desired_norm:
                return True
        
        for c in candidates:
            norm = c.casefold()
            if desired_norm in norm or norm in desired_norm:
                return True

        return False

    # =========================================================================
    # Métodos internos
    # =========================================================================
    
    def _register_new_outbound(self, raw_uri: str, outbound: Outbound) -> None:
        """Atualiza estruturas internas quando novo outbound é aceito."""
        index = len(self._outbounds) - 1
        entry = self._make_base_entry(index, raw_uri, outbound)
        
        if self._cache.enabled:
            cached = self._cache.get(raw_uri)
            if cached:
                entry = self._cache.apply_to_entry(entry, cached)
                entry["country_match"] = self.matches_country(entry, self.country_filter)
        
        self._entries.append(entry)
    
    def _prime_entries_from_cache(self) -> None:
        """Reconstrói registros a partir do cache."""
        if not self._cache.enabled:
            return
        
        rebuilt: List[Dict[str, Any]] = []
        for idx, (raw_uri, outbound) in enumerate(self._outbounds):
            entry = self._make_base_entry(idx, raw_uri, outbound)
            cached = self._cache.get(raw_uri)
            if cached:
                entry = self._cache.apply_to_entry(entry, cached)
                entry["country_match"] = self.matches_country(entry, self.country_filter)
            rebuilt.append(entry)
        
        self._entries = rebuilt
    
    def _make_base_entry(
        self, 
        index: int, 
        raw_uri: str, 
        outbound: Outbound
    ) -> Dict[str, Any]:
        """Monta dicionário padrão para um outbound."""
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
    
    def _read_source_text(self, source: str) -> str:
        """Obtém conteúdo de arquivo local ou URL."""
        # Arquivo local
        if not re.match(r"^https?://", source, re.I):
            logger.info(f"Lendo arquivo local: {source}")
            path = Path(source)
            return decode_bytes(path.read_bytes())
        
        # URL
        if self.requests is None:
            raise RuntimeError(
                "O pacote requests não está disponível. "
                "Instale com: pip install requests"
            )
        
        # GitHub API
        if self._is_github_api_url(source):
            return self._fetch_github_api_content(source)
        
        # URL genérica
        logger.info(f"Baixando conteúdo de URL: {source}")
        try:
            resp = self.requests.get(source, timeout=30)
            resp.raise_for_status()
            return decode_bytes(resp.content, encoding_hint=resp.encoding)
        except self.requests.exceptions.Timeout:
            raise RuntimeError(f"Timeout ao acessar {source}")
        except self.requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f"Erro de conexão ao acessar {source}") from exc
    
    def _is_github_api_url(self, url: str) -> bool:
        """Verifica se é URL da API do GitHub."""
        return bool(re.match(r"^https://api\.github\.com/repos/.+/contents/.+", url, re.I))
    
    def _fetch_github_api_content(self, api_url: str) -> str:
        """Busca e decodifica conteúdo da API do GitHub."""
        import base64
        import json
        
        logger.info(f"Buscando da API do GitHub: {api_url}")
        
        try:
            resp = self.requests.get(
                api_url,
                timeout=30,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Raxy-Proxy-Manager/1.0"
                }
            )
            
            if resp.status_code == 403:
                raise RuntimeError("Rate limit da API do GitHub excedido")
            if resp.status_code == 404:
                raise RuntimeError(f"Recurso não encontrado: {api_url}")
            
            resp.raise_for_status()
            
            api_response = resp.json()
            content_b64 = api_response.get("content", "")
            cleaned = content_b64.replace("\n", "").replace("\r", "").strip()
            
            return base64.b64decode(cleaned).decode("utf-8")
            
        except self.requests.exceptions.Timeout:
            raise RuntimeError("Timeout ao acessar API do GitHub")
        except self.requests.exceptions.ConnectionError as exc:
            raise RuntimeError("Erro de conexão ao acessar API do GitHub") from exc
    
    def _perform_health_checks(
        self,
        outbounds: List[Tuple[str, Outbound]],
        *,
        country_filter: Optional[str] = None,
        emit_progress: Optional[ProxyDisplayManager] = None,
        force_refresh: bool = False,
        functional_timeout: float = 10.0,
        threads: int = 1,
        stop_on_success: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Testa outbounds de forma concorrente."""
        all_results: List[Dict[str, Any]] = []
        reuse_cache = self._cache.enabled and not force_refresh
        success_count = 0

        to_test: List[Tuple[int, str, Outbound]] = []
        
        # Primeiro processa cache
        for idx, (raw, outbound) in enumerate(outbounds):
            base_entry = self._make_base_entry(idx, raw, outbound)
            
            if reuse_cache:
                cached_data = self._cache.get(raw)
                if cached_data:
                    entry = self._cache.apply_to_entry(base_entry, cached_data)
                    
                    if country_filter and entry.get("status") == "OK":
                        entry["country_match"] = self.matches_country(entry, country_filter)
                        if not entry["country_match"]:
                            entry["status"] = "FILTRADO"
                            exit_country = entry.get("proxy_country") or entry.get("country") or "-"
                            entry["error"] = f"Filtro '{country_filter}': País de saída é {exit_country}"
                    
                    all_results.append(entry)

                    if entry.get("status") == "OK":
                        success_count += 1

                    if emit_progress:
                        emit_progress.emit_test_progress(entry, len(all_results), len(outbounds))
                    continue
            
            to_test.append((idx, raw, outbound))

        # Verifica se já atingiu limite
        limit_reached = stop_on_success is not None and stop_on_success > 0
        if limit_reached and success_count >= stop_on_success:
            if self._display.enabled:
                self._display.print(
                    f"\n[bold green]Encontradas {success_count} proxies válidas no cache.[/]"
                )
            for idx, raw, outbound in to_test:
                all_results.append(self._make_base_entry(idx, raw, outbound))
            all_results.sort(key=lambda x: x.get("index", float('inf')))
            return all_results
        
        # Testa proxies não em cache
        if to_test:
            if self._display.enabled:
                self._display.print(
                    f"\n[yellow]Iniciando teste de {len(to_test)} proxies "
                    f"com {threads} workers...[/]"
                )
            
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {
                    executor.submit(
                        self._test_single_outbound,
                        idx, raw, outbound, functional_timeout, country_filter
                    ): idx
                    for idx, raw, outbound in to_test
                }
                tested_indices: set[int] = set()

                for future in as_completed(futures):
                    try:
                        result_entry = future.result()
                        all_results.append(result_entry)
                        tested_indices.add(result_entry["index"])

                        if emit_progress:
                            emit_progress.emit_test_progress(
                                result_entry, len(all_results), len(outbounds)
                            )
                        
                        if result_entry.get("status") == "OK":
                            success_count += 1
                        
                        if limit_reached and success_count >= stop_on_success:
                            if self._display.enabled:
                                self._display.print(
                                    f"\n[bold green]Limite de {stop_on_success} proxies atingido.[/]"
                                )
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            break
                    except Exception as exc:
                        if self._display.enabled:
                            self._display.print(f"[bold red]Erro em thread: {exc}[/]")

                # Adiciona não testados
                for idx, raw, outbound in to_test:
                    if idx not in tested_indices:
                        all_results.append(self._make_base_entry(idx, raw, outbound))

        all_results.sort(key=lambda x: x.get("index", float('inf')))
        return all_results
    
    def _test_single_outbound(
        self,
        idx: int,
        raw_uri: str,
        outbound: Outbound,
        timeout: float,
        country_filter: Optional[str]
    ) -> Dict[str, Any]:
        """Testa um outbound individual."""
        entry = self._make_base_entry(idx, raw_uri, outbound)
        
        try:
            host, port = self._outbound_host_port(outbound)
            entry.update({"host": host, "port": port})
        except Exception:
            pass
        
        entry["status"] = "TESTANDO"

        result = self._test_outbound(raw_uri, outbound, timeout=timeout)
        finished_at = time.time()

        entry.update({
            "host": result.get("host") or entry["host"],
            "port": result.get("port") if result.get("port") is not None else entry["port"],
            "ip": result.get("ip") or entry["ip"],
            "country": result.get("country") or entry["country"],
            "country_code": result.get("country_code"),
            "country_name": result.get("country_name"),
            "ping": result.get("ping_ms"),
            "tested_at_ts": finished_at,
            "tested_at": format_timestamp(finished_at),
            "functional": result.get("functional", False),
            "external_ip": result.get("external_ip"),
            "proxy_ip": result.get("proxy_ip"),
            "proxy_country": result.get("proxy_country"),
            "proxy_country_code": result.get("proxy_country_code"),
        })

        if entry["functional"]:
            entry["status"] = "OK"
            entry["error"] = None
        else:
            entry["status"] = "ERRO"
            entry["error"] = result.get("error", "Teste falhou")

        if country_filter and entry["status"] == "OK":
            entry["country_match"] = self.matches_country(entry, country_filter)
            if not entry["country_match"]:
                entry["status"] = "FILTRADO"
                exit_country = entry.get("proxy_country") or entry.get("country") or "-"
                entry["error"] = f"Filtro '{country_filter}': País de saída é {exit_country}"
        
        return entry
    
    def _test_outbound(
        self, 
        raw_uri: str, 
        outbound: Outbound, 
        timeout: float = 10.0
    ) -> Dict[str, Any]:
        """Executa teste real de um outbound via ponte temporária."""
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

        # Resolve IP
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

        # Lookup país do servidor
        if result.get("ip"):
            country_info = self._lookup_country(result["ip"])
            if country_info:
                result["country"] = country_info.get("label")
                result["country_code"] = country_info.get("code")
                result["country_name"] = country_info.get("name")

        # Teste funcional via ponte
        func_result = self._test_proxy_functionality(raw_uri, outbound, timeout=timeout)
        
        if func_result.get("functional"):
            result["ping_ms"] = func_result.get("response_time")
            result["functional"] = True
            result["external_ip"] = func_result.get("external_ip")
            
            # Verifica se IP de saída é diferente do servidor
            if func_result.get("external_ip") and func_result["external_ip"] != result.get("ip"):
                result["proxy_ip"] = func_result["external_ip"]
                proxy_country = self._lookup_country(func_result["external_ip"])
                if proxy_country:
                    result["proxy_country"] = proxy_country.get("label")
                    result["proxy_country_code"] = proxy_country.get("code")
        else:
            result["error"] = func_result.get("error", "Proxy não funcional")
            result["functional"] = False

        return result
    
    @contextmanager
    def _temporary_bridge(
        self,
        outbound: Outbound,
        *,
        tag_prefix: str = "temp",
    ) -> Iterator[Tuple[int, Any]]:
        """Cria ponte Xray temporária garantindo limpeza de recursos."""
        port: Optional[int] = None
        proc = None
        cfg_dir: Optional[Path] = None

        try:
            port = self._bridge_manager.find_available_port()
            cfg = self._bridge_manager.make_xray_config(port, outbound)
            xray_bin = self._bridge_manager.which_xray()
            
            proc, cfg_path = self._bridge_manager.launch_bridge(
                xray_bin, cfg, f"{tag_prefix}_{outbound.tag}"
            )
            cfg_dir = cfg_path.parent

            time.sleep(1.0)
            if proc.poll() is not None:
                error_output = ""
                if proc.stderr:
                    error_output = decode_bytes(proc.stderr.read()).strip()
                
                raise RuntimeError(
                    f"Xray finalizou antes do teste. Erro: {error_output or 'Nenhum'}"
                )

            yield port, proc
        finally:
            self._bridge_manager._terminate_process(proc, wait_timeout=2)
            self._bridge_manager._safe_remove_dir(cfg_dir)
            if port is not None:
                self._bridge_manager.release_port(port)
    
    def _test_proxy_functionality(
        self, 
        raw_uri: str, 
        outbound: Outbound,
        timeout: float = 10.0,
        test_url: str = "http://httpbin.org/ip"
    ) -> Dict[str, Any]:
        """Testa funcionalidade real via requisição HTTP."""
        result: Dict[str, Any] = {
            "functional": False,
            "response_time": None,
            "external_ip": None,
            "error": None
        }
        
        if self.requests is None:
            result["error"] = "requests não disponível"
            return result
        
        response = None
        duration_ms: Optional[float] = None

        try:
            with self._temporary_bridge(outbound, tag_prefix="test") as (test_port, _):
                proxy_url = f"http://127.0.0.1:{test_port}"
                proxies = {"http": proxy_url, "https": proxy_url}
                start_time = time.perf_counter()
                
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36"
                    )
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
        except self.requests.exceptions.Timeout:
            result["error"] = f"Timeout após {timeout:.1f}s"
            return result
        except self.requests.exceptions.ProxyError as exc:
            result["error"] = f"Erro de proxy: {str(exc)[:100]}"
            return result
        except self.requests.exceptions.ConnectionError as exc:
            result["error"] = f"Erro de conexão: {str(exc)[:100]}"
            return result
        except Exception as exc:
            result["error"] = f"Erro: {str(exc)[:100]}"
            return result

        result["functional"] = True
        result["response_time"] = duration_ms
        
        if response is not None:
            try:
                data = response.json()
                origin = data.get("origin")
                if isinstance(origin, str) and origin.strip():
                    result["external_ip"] = origin.split(",")[0].strip()
            except Exception:
                pass
        
        return result
    
    def _outbound_host_port(self, outbound: Outbound) -> Tuple[str, int]:
        """Extrai host e porta do outbound."""
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
            raise ValueError(f"Protocolo não suportado: {proto}")

        if host is None or port is None:
            raise ValueError(f"Host/port ausentes no outbound {outbound.tag}")
        
        return host, int(str(port).strip())
    
    def _lookup_country(self, ip: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
        """Consulta localização do IP com fallback para IP-API."""
        if not ip or self.requests is None:
            return None
        
        # Ignora IPs locais para evitar chamadas de API desnecessárias
        if not is_public_ip(ip):
            return None
        
        # 1. Tenta FindIP se configurado (prioridade)
        try:
            # Tenta importar do local correto
            try:
                from raxy.config import get_config
            except ImportError:
                # Fallback antigo se existir
                from raxy.infrastructure.config.config import get_config
                
            config = get_config()
            token = config.api.findip_token if config and config.api else ""
            
            if token:
                resp = self.requests.get(
                    f"https://api.findip.net/{ip}/?token={token}", 
                    timeout=5
                )
                resp.raise_for_status()
                data = resp.json()
                country_info = data.get("country", {})
                return {
                    "name": country_info.get("names", {}).get("en"),
                    "code": country_info.get("iso_code"),
                    "label": country_info.get("names", {}).get("en") or country_info.get("iso_code")
                }
        except Exception:
            pass # Falha silenciosa no FindIP, tenta próximo

        # 2. Fallback: IP-API.com (Gratuito, sem token, rate limited)
        try:
            resp = self.requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") == "success":
                return {
                    "name": data.get("country"),
                    "code": data.get("countryCode"),
                    "label": data.get("country") or data.get("countryCode")
                }
        except Exception:
            pass

        return None


# Backward compatibility: exporta STATUS_STYLES como atributo de classe
ProxyManager.STATUS_STYLES = ProxyDisplayManager.STATUS_STYLES
