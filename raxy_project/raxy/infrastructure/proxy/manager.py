# -*- coding: utf-8 -*-
"""Ferramenta orientada a biblioteca para testar e criar pontes HTTP para proxys V2Ray/Xray.

O módulo expõe a classe :class:`Proxy`, que gerencia carregamento de links, testes
com filtragem opcional por país e criação de túneis HTTP locais utilizando Xray ou
V2Ray. Todo o comportamento é pensado para uso programático em outros módulos.
"""

from __future__ import annotations

import atexit
import logging
import os
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from raxy.interfaces.services import IProxyService
from raxy.core.logging import debug_log, get_logger
from raxy.interfaces.services.IProxyComponents import IProxyProcessManager, IProxyNetworkManager
from raxy.models.proxy import Outbound, BridgeRuntime, ProxyItem, ProxyTestResult
from .parser import parse_uri_to_outbound
from .storage import (
    DEFAULT_CACHE_FILENAME,
    load_cache,
    save_cache,
    make_base_entry,
    apply_cached_entry,
    format_timestamp
)

__all__ = ["Proxy"]

# Configuração de logging
logger = get_logger()

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


class Proxy(IProxyService):
    """Gerencia uma coleção de proxys, com suporte a testes e criação de pontes HTTP."""

    STATUS_STYLES: Dict[str, str] = {
        "AGUARDANDO": "dim",
        "TESTANDO": "yellow",
        "OK": "bold green",
        "ERRO": "bold red",
        "FILTRADO": "cyan",
    }

    # Expose these for compatibility if anyone used Proxy.Outbound/BridgeRuntime
    Outbound = Outbound
    BridgeRuntime = BridgeRuntime

    def __init__(
        self,
        process_manager: IProxyProcessManager,
        network_manager: IProxyNetworkManager,
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
        
        self.process = process_manager
        self.network = network_manager

        self._outbounds: List[Tuple[str, Outbound]] = []
        self._entries: List[ProxyItem] = []
        self._bridges: List[BridgeRuntime] = []
        self._running = False
        self._atexit_registered = False
        self._parse_errors: List[str] = []

        self.use_cache = use_cache
        default_cache_path = Path(__file__).with_name(DEFAULT_CACHE_FILENAME)
        self.cache_path = Path(cache_path) if cache_path is not None else default_cache_path
        self._cache_entries: Dict[str, ProxyTestResult] = {}
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

    def _register_new_outbound(self, raw_uri: str, outbound: Outbound) -> None:
        """Atualiza as estruturas internas quando um novo outbound é aceito."""
        index = len(self._outbounds)
        # Import replace locally or at top level. Let's assume replace is available or import it.
        from dataclasses import replace
        
        entry = make_base_entry(index, raw_uri, outbound)
        if self.use_cache and self._cache_entries:
            cached = self._cache_entries.get(raw_uri)
            if cached:
                entry = apply_cached_entry(entry, cached)
                match = self.matches_country(entry, self.country_filter)
                # Update result with match
                entry = replace(entry, result=replace(entry.result, country_match=match))
        self._entries.append(entry)

    def _prime_entries_from_cache(self) -> None:
        """Reconstrói os registros a partir do cache sem repetir parsing."""
        if not self.use_cache or not self._cache_entries:
            return
        
        from dataclasses import replace
        rebuilt: List[ProxyItem] = []
        for idx, (raw_uri, outbound) in enumerate(self._outbounds):
            entry = make_base_entry(idx, raw_uri, outbound)
            cached = self._cache_entries.get(raw_uri)
            if cached:
                entry = apply_cached_entry(entry, cached)
                match = self.matches_country(entry, self.country_filter)
                entry = replace(entry, result=replace(entry.result, country_match=match))
            rebuilt.append(entry)
        self._entries = rebuilt

    def _load_cache(self) -> None:
        """Carrega resultados persistidos anteriormente para acelerar novos testes."""
        if not self.use_cache:
            return
        self._cache_entries = load_cache(self.cache_path)
        if self._cache_entries:
            self._cache_available = True

    def _save_cache(self, entries: List[ProxyItem]) -> None:
        """Persiste a última bateria de testes para acelerar execuções futuras."""
        if not self.use_cache:
            return
        save_cache(self.cache_path, entries)

    @staticmethod
    def _format_destination(host: Optional[str], port: Optional[int]) -> str:
        """Monta representação amigável para host:porta exibida em tabelas."""
        if not host or host == "-":
            return "-"
        if port is None:
            return host
        return f"{host}:{port}"

    @staticmethod
    def _check_country_match(country_info: Dict[str, Any], desired: Optional[str]) -> bool:
        """Helper que verifica se um conjunto específico de campos de país corresponde ao país desejado."""
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

    @classmethod
    def matches_country(cls, entry: ProxyItem, desired: Optional[str]) -> bool:
        """Valida se o registro atende ao filtro de país, exigindo que tanto o servidor quanto a saída correspondam."""
        if not desired:
            return True

        # Define informações para os locais de saída e do servidor
        exit_country_info = {
            "country": entry.result.proxy_country,
            "country_code": entry.result.proxy_country_code,
        }
        server_country_info = {
            "country": entry.result.country,
            "country_code": entry.result.country_code,
            "country_name": entry.result.country_name,
        }

        # A localização efetiva é a de saída se existir, senão, a do servidor
        effective_exit_info = exit_country_info if exit_country_info.get("country") else server_country_info
        
        # Regra 1: A localização de saída efetiva DEVE corresponder
        if not cls._check_country_match(effective_exit_info, desired):
            return False
            
        # Regra 2: Se o servidor e a saída são diferentes, o servidor TAMBÉM DEVE corresponder
        if entry.result.proxy_ip and entry.result.proxy_ip != entry.result.ip:
            if not cls._check_country_match(server_country_info, desired):
                return False
                
        # Se passou em todas as verificações, é uma correspondência válida
        return True

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
                outbound = parse_uri_to_outbound(line)
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
            text = self.network.read_source_text(src)
            lines = [ln.strip() for ln in text.splitlines()]
            added += self.add_proxies(lines)
        return added

    # ----------- verificação e filtros -----------

    def _perform_health_checks(
        self,
        outbounds: List[Tuple[str, Outbound]],
        *,
        country_filter: Optional[str] = None,
        emit_progress: Optional[Any] = None,
        force_refresh: bool = False,
        functional_timeout: float = 10.0,
        threads: int = 1,
        stop_on_success: Optional[int] = None,
    ) -> List[ProxyItem]:
        """Percorre os outbounds testando conectividade real de forma concorrente."""
        all_results: List[ProxyItem] = []
        reuse_cache = self.use_cache and not force_refresh
        success_count = 0

        to_test: List[Tuple[int, str, Outbound]] = []
        
        from dataclasses import replace
        
        for idx, (raw, outbound) in enumerate(outbounds):
            base_entry = make_base_entry(idx, raw, outbound)
            
            if reuse_cache and raw in self._cache_entries:
                cached_data = self._cache_entries[raw]
                entry = apply_cached_entry(base_entry, cached_data)
                
                if country_filter and entry.result.status == "OK":
                    match = self.matches_country(entry, country_filter)
                    entry.result.country_match = match
                    if not match:
                        entry.result.status = "FILTRADO"
                        exit_country = entry.result.proxy_country or entry.result.country or "-"
                        server_country = entry.result.country or "-"
                        if exit_country != server_country:
                             entry.result.error = f"Filtro '{country_filter}': Servidor ({server_country}) ou Saída ({exit_country}) não correspondem"
                        else:
                             entry.result.error = f"Filtro '{country_filter}': País de saída é {exit_country}"
                
                all_results.append(entry)

                if entry.result.status == "OK":
                    success_count += 1

                if emit_progress:
                    self._emit_test_progress(entry, len(all_results), len(outbounds), emit_progress)
            else:
                to_test.append((idx, raw, outbound))

        limit_reached = stop_on_success is not None and stop_on_success > 0
        if limit_reached and success_count >= stop_on_success:
            if self.console:
                self.console.print(f"[bold green]Encontradas {success_count} proxies válidas no cache, atingindo o limite de {stop_on_success}. Testes adicionais ignorados.[/]")
            for idx, raw, outbound in to_test:
                all_results.append(make_base_entry(idx, raw, outbound))
            all_results.sort(key=lambda x: x.index)
            return all_results
        
        if to_test:
            def worker(idx: int, raw: str, outbound: Outbound) -> ProxyItem:
                entry = make_base_entry(idx, raw, outbound)
                try:
                    preview_host, preview_port = self.network.outbound_host_port(outbound)
                    entry.host = preview_host
                    entry.port = preview_port
                except Exception:
                    pass
                entry.result.status = "TESTANDO"

                result = self.network.test_outbound(raw, outbound, timeout=functional_timeout)
                finished_at = time.time()
                
                # Update ProxyItem fields
                entry.host = result.get("host") or entry.host
                if result.get("port") is not None:
                     entry.port = result.get("port")
                
                # Update ProxyTestResult fields
                res = entry.result
                res.ip = result.get("ip") or res.ip
                res.country = result.get("country") or res.country
                res.country_code = result.get("country_code") or res.country_code
                res.country_name = result.get("country_name") or res.country_name
                res.ping_ms = result.get("ping_ms")
                res.tested_at_ts = finished_at
                res.tested_at = format_timestamp(finished_at)
                res.functional = result.get("functional", False)
                res.external_ip = result.get("external_ip")
                res.proxy_ip = result.get("proxy_ip")
                res.proxy_country = result.get("proxy_country")
                res.proxy_country_code = result.get("proxy_country_code")

                if res.functional:
                    res.status = "OK"
                    res.error = None
                else:
                    res.status = "ERRO"
                    res.error = result.get("error", "Teste falhou")

                if country_filter and res.status == "OK":
                    res.country_match = self.matches_country(entry, country_filter)
                    if not res.country_match:
                        res.status = "FILTRADO"
                        exit_country = res.proxy_country or res.country or "-"
                        server_country = res.country or "-"
                        if exit_country != server_country:
                             res.error = f"Filtro '{country_filter}': Servidor ({server_country}) ou Saída ({exit_country}) não correspondem"
                        else:
                             res.error = f"Filtro '{country_filter}': País de saída é {exit_country}"
                
                return entry

            if self.console:
                self.console.print(f"[yellow]Iniciando teste de {len(to_test)} proxies com até {threads} workers...[/]")
            
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {executor.submit(worker, idx, raw, outbound) for idx, raw, outbound in to_test}
                tested_indices = set()

                for future in as_completed(futures):
                    try:
                        result_entry = future.result()
                        all_results.append(result_entry)
                        tested_indices.add(result_entry.index)

                        if emit_progress:
                            self._emit_test_progress(result_entry, len(all_results), len(outbounds), emit_progress)
                        
                        if result_entry.result.status == "OK":
                            success_count += 1
                        
                        if limit_reached and success_count >= stop_on_success:
                            if self.console:
                                self.console.print(f"[bold green]Limite de {stop_on_success} proxies encontradas. Finalizando testes.[/]")
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            break
                    except Exception as exc:
                        if self.console:
                            self.console.print(f"[bold red]Erro fatal em uma thread de teste: {exc}[/]")

                for idx, raw, outbound in to_test:
                    if idx not in tested_indices:
                        all_results.append(make_base_entry(idx, raw, outbound))

        all_results.sort(key=lambda x: x.index)
        return all_results

    # ----------- interface pública -----------

    @property
    def entries(self) -> List[ProxyItem]:
        """Retorna os registros carregados ou decorrentes dos últimos testes."""
        return self._entries

    @property
    def parse_errors(self) -> List[str]:
        """Lista de linhas ignoradas ao interpretar os links informados."""
        return list(self._parse_errors)

    def _emit_test_progress(self, entry: ProxyItem, count: int, total: int, emit_progress: Any) -> None:
        """Emite informações de progresso do teste."""
        destino = self._format_destination(entry.host, entry.port)
        ping_preview = entry.result.ping_ms
        ping_fmt = f"{ping_preview:.1f} ms" if isinstance(ping_preview, (int, float)) else "-"
        
        status_fmt = {
            "OK": "[bold green]OK[/]",
            "ERRO": "[bold red]ERRO[/]",
            "TESTANDO": "[yellow]TESTANDO[/]",
            "AGUARDANDO": "[dim]AGUARDANDO[/]",
            "FILTRADO": "[cyan]FILTRADO[/]",
        }.get(entry.result.status, entry.result.status)
        
        cache_note = ""
        if entry.result.cached:
            cache_note = " [dim](cache)[/]" if Console else " (cache)"
        
        display_country = entry.result.proxy_country or entry.result.country or "-"
        
        emit_progress.print(
            f"[{count}/{total}] {status_fmt}{cache_note} [bold]{entry.tag}[/] -> "
            f"{destino} | IP: {entry.result.ip or '-'} | "
            f"País: {display_country} | Ping: {ping_fmt}"
        )
        
        if entry.result.proxy_ip and entry.result.proxy_ip != entry.result.ip:
            original_country = entry.result.country or "-"
            emit_progress.print(
                f"    [dim]País do Servidor: {original_country} -> "
                f"País de Saída: {entry.result.proxy_country}[/]"
            )
        
        if entry.result.error:
            emit_progress.print(f"    [dim]Motivo: {entry.result.error}[/]")

    def test(
        self,
        *,
        threads: Optional[int] = 1,
        country: Optional[str] = None,
        verbose: Optional[bool] = None,
        timeout: float = 10.0,
        force: bool = False,
        find_first: Optional[int] = None,
    ) -> List[ProxyItem]:
        """Testa as proxies carregadas usando rota real para medir ping."""
        if not self._outbounds:
            raise RuntimeError("Nenhuma proxy carregada para testar.")

        country_filter = country if country is not None else self.country_filter
        emit = self.console if (self.console is not None and (verbose is None or verbose)) else None

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
        self._save_cache(results)

        if self.console is not None and (verbose is None or verbose):
            self._render_test_summary(results, country_filter)

        return results

    def _render_test_summary(self, entries: List[ProxyItem], country_filter: Optional[str]) -> None:
        """Exibe relatório amigável via Rich quando disponível."""
        if not self.console or Table is None:
            return
        
        ok_entries = [e for e in entries if e.result.status == "OK"]
        if country_filter:
            table_entries = [entry for entry in ok_entries if entry.result.country_match]
        else:
            table_entries = ok_entries

        self.console.print()
        self.console.rule("Proxies Funcionais")
        if table_entries:
            self.console.print(self._render_test_table(table_entries))
        else:
            msg = "[yellow]Nenhuma proxy funcional encontrada.[/yellow]"
            if country_filter:
                 msg = f"[yellow]Nenhuma proxy funcional corresponde ao filtro de país '{country_filter}'.[/yellow]"
            self.console.print(msg)

        success = sum(1 for entry in entries if entry.result.status == "OK")
        fail = sum(1 for entry in entries if entry.result.status == "ERRO")
        filtered = sum(1 for entry in entries if entry.result.status == "FILTRADO")

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
            if entry.result.status == "ERRO" and entry.result.error
        ]
        if failed_entries:
            self.console.print()
            self.console.print("[bold red]Detalhes das falhas:[/]")
            for entry in failed_entries[:10]:
                self.console.print(f" - [bold]{entry.tag or '-'}[/]: {entry.result.error}")
            if len(failed_entries) > 10:
                self.console.print(f"  [dim]... e mais {len(failed_entries) - 10} outras falhas.[/dim]")


    @staticmethod
    def _render_test_table(entries: List[ProxyItem]):
        """Gera uma tabela Rich com o resultado dos testes."""
        if Table is None:
            raise RuntimeError("render_test_table requer a biblioteca 'rich'.")
        
        entries.sort(key=lambda e: e.result.ping_ms or float('inf'))

        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Tag", no_wrap=True, max_width=30)
        table.add_column("Destino", overflow="fold")
        table.add_column("IP Real (Saída)", no_wrap=True)
        table.add_column("País (Saída)", no_wrap=True)
        table.add_column("Ping", justify="right", no_wrap=True)
        for entry in entries:
            status = entry.result.status
            style = Proxy.STATUS_STYLES.get(status, "white")
            status_cell = Text(status, style=style) if Text else status
            destino = Proxy._format_destination(entry.host, entry.port)
            ping = entry.result.ping_ms
            ping_str = f"{ping:.1f} ms" if isinstance(ping, (int, float)) else "-"
            
            display_ip = entry.result.proxy_ip or entry.result.ip or "-"
            display_country = entry.result.proxy_country or entry.result.country or "-"
            
            table.add_row(
                status_cell,
                (entry.tag or "-"),
                destino,
                display_ip,
                display_country,
                ping_str,
            )
        return table

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
    ) -> List[ProxyItem]:
        """Cria pontes HTTP locais para as proxys aprovadas opcionalmente testando antes."""
        if self._running:
            raise RuntimeError("As pontes já estão em execução. Chame stop() antes de iniciar novamente.")
        if not self._outbounds:
            raise RuntimeError("Nenhuma proxy carregada para iniciar.")

        country_filter = country if country is not None else self.country_filter
        
        if auto_test:
            self.test(
                threads=threads,
                country=country_filter,
                verbose=self.use_console,
                find_first=find_first
            )
            country_filter = self.country_filter

        approved_entries = [
            entry for entry in self._entries
            if entry.result.status == "OK" 
            and self.matches_country(entry, country_filter)
        ]
        
        def get_ping_for_sort(entry: ProxyItem) -> float:
            ping = entry.result.ping_ms
            return float(ping) if isinstance(ping, (int, float)) else float('inf')
        
        approved_entries.sort(key=get_ping_for_sort)
        
        if not approved_entries:
            if country_filter:
                raise RuntimeError(
                    f"Nenhuma proxy aprovada para o país '{country_filter}'. "
                    "Execute o teste e verifique os resultados."
                )
            else:
                raise RuntimeError("Nenhuma proxy aprovada para iniciar. Execute test() e verifique os resultados.")

        if amounts is not None:
            if not isinstance(amounts, int) or amounts <= 0:
                raise ValueError("amounts deve ser um inteiro positivo.")
            if amounts < len(approved_entries):
                approved_entries = approved_entries[:amounts]
            elif amounts > len(approved_entries) and self.console:
                self.console.print(
                    f"Atenção: solicitado amounts={amounts} mas só existem {len(approved_entries)} "
                    f"proxies aprovadas{f' para {country_filter}' if country_filter else ''}. "
                    "Iniciando todas as disponíveis."
                )

        xray_bin = self.process.which_xray()

        self._stop_event.clear()
        bridges_runtime: List[BridgeRuntime] = []
        bridges_display: List[Tuple[BridgeRuntime, float]] = []

        if self.console and approved_entries:
            self.console.print()
            self.console.print(
                f"[green]Iniciando {len(approved_entries)} pontes ordenadas por ping[/]"
            )

        try:
            for entry in approved_entries:
                # O índice do entry deve corresponder ao índice em self._outbounds, mas self._outbounds é lista.
                # entry.index é confiável.
                raw_uri, outbound = self._outbounds[entry.index]
                
                port = self.process.find_available_port()
                cfg = self.process.make_xray_config_http_inbound(port, outbound)
                scheme = raw_uri.split("://", 1)[0].lower()

                proc, cfg_path = self.process.launch_bridge_with_diagnostics(xray_bin, cfg, outbound.tag)
                bridge = BridgeRuntime(
                    tag=outbound.tag,
                    port=port,
                    scheme=scheme,
                    uri=raw_uri,
                    process=proc,
                    workdir=cfg_path.parent,
                )
                bridges_runtime.append(bridge)
                bridges_display.append((bridge, get_ping_for_sort(entry)))
        except Exception:
            for bridge in bridges_runtime:
                self.process.terminate_process(bridge.process)
                self.process.safe_remove_dir(bridge.workdir)
                self.process.release_port(bridge.port)
            raise

        self._bridges = bridges_runtime
        self._running = True

        if not self._atexit_registered:
            import atexit
            atexit.register(self.stop)
            self._atexit_registered = True

        if self.console:
            self.console.print()
            self.console.rule(f"Pontes HTTP ativas{f' - País: {country_filter}' if country_filter else ''} - Ordenadas por Ping")
            for idx, (bridge, ping) in enumerate(bridges_display):
                ping_str = f"{ping:6.1f}ms" if ping != float('inf') else "     -     "
                self.console.print(
                    f"[bold cyan]ID {idx:<2}[/] http://127.0.0.1:{bridge.port}  ->  [{ping_str}]"
                )

            self.console.print()
            self.console.print("Pressione Ctrl+C para encerrar todas as pontes.")

        active_proxies = []
        from dataclasses import replace
        for entry, bridge in zip(approved_entries, bridges_runtime):
            # Retorna um ProxyItem modificado onde a URI é a da ponte local.
            # Isso permite que serviços utilizem o objeto diretamente.
            active_item = replace(entry, uri=bridge.url)
            active_proxies.append(active_item)

        if wait:
            self.wait()
        else:
            self._start_wait_thread()

        return active_proxies

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
            pass

    def wait(self) -> None:
        """Bloqueia até que todas as pontes terminem ou ``stop`` seja chamado."""
        if not self._running:
            raise RuntimeError("Nenhuma ponte ativa para aguardar.")
        try:
            while not self._stop_event.is_set():
                alive = any(
                    bridge.process and bridge.process.poll() is None
                    for bridge in self._bridges
                )
                if not alive:
                    if self.console:
                        self.console.print("[yellow]Todos os processos xray finalizaram.[/yellow]")
                    break
                time.sleep(0.5)
        except KeyboardInterrupt:
            if self.console:
                self.console.print("[yellow]Interrupção recebida, encerrando pontes...[/yellow]")
        finally:
            self.stop()

    def stop(self) -> None:
        """Finaliza processos Xray ativos e limpa arquivos temporários."""
        if not self._running and not self._bridges:
            return

        self._stop_event.set()
        
        bridges_to_stop = list(self._bridges)
        if bridges_to_stop:
            for bridge in bridges_to_stop:
                self.process.terminate_process(bridge.process)
                self.process.safe_remove_dir(bridge.workdir)
                self.process.release_port(bridge.port)

        self._bridges = []
        self._running = False

        if self._wait_thread and self._wait_thread is not threading.current_thread():
            self._wait_thread.join(timeout=1.0)
        self._wait_thread = None

    def get_http_proxy(self) -> List[Dict[str, Any]]:
        """Retorna ID, URL local e URI de cada ponte em execução."""
        if not self._running:
            return []
        return [
            {"id": idx, "url": bridge.url, "uri": bridge.uri}
            for idx, bridge in enumerate(self._bridges)
        ]

    def rotate_proxy(self, bridge_id: int) -> bool:
        """Troca a proxy de uma ponte em execução por outra proxy aleatória e funcional."""
        
        if not self._running or not (0 <= bridge_id < len(self._bridges)):
            if self.console:
                msg = f"ID de ponte inválido: {bridge_id}. IDs válidos: 0 a {len(self._bridges) - 1}."
                self.console.print(f"[red]Erro: {msg}[/red]")
            return False

        bridge = self._bridges[bridge_id]
        uri_to_replace = bridge.uri

        # Encontra a entrada correspondente na lista principal e a invalida
        entry_to_invalidate = next((e for e in self._entries if e.uri == uri_to_replace), None)
        if entry_to_invalidate:
            entry_to_invalidate.result.status = "ERRO"
            entry_to_invalidate.result.error = "Proxy invalidada manualmente via rotação"
            entry_to_invalidate.result.tested_at_ts = time.time() # Atualiza o timestamp
            self._save_cache(self._entries) # Salva o cache com a proxy invalidada
            if self.console:
                self.console.print(f"[dim]Proxy '{bridge.tag}' marcada como inválida no cache.[/dim]")

        candidates = [
            entry for entry in self._entries
            if entry.result.status == "OK"
            and self.matches_country(entry, self.country_filter)
            and entry.uri != uri_to_replace
        ]

        if not candidates:
            if self.console:
                self.console.print(f"[yellow]Aviso: Nenhuma outra proxy disponível para rotacionar a ponte ID {bridge_id}.[/yellow]")
            return False

        new_entry = random.choice(candidates)
        new_raw_uri = new_entry.uri
        new_outbound = new_entry.outbound

        self.process.terminate_process(bridge.process, wait_timeout=2)
        self.process.safe_remove_dir(bridge.workdir)

        try:
            xray_bin = self.process.which_xray()
            cfg = self.process.make_xray_config_http_inbound(bridge.port, new_outbound)
            new_proc, new_cfg_path = self.process.launch_bridge_with_diagnostics(xray_bin, cfg, new_outbound.tag)
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Falha ao reiniciar ponte {bridge_id} na porta {bridge.port}: {e}[/red]")
            bridge.process = None # Marca a ponte como inativa
            return False

        self._bridges[bridge_id] = BridgeRuntime(
            tag=new_outbound.tag,
            port=bridge.port,
            scheme=new_scheme,
            uri=new_raw_uri,
            process=new_proc,
            workdir=new_cfg_path.parent,
        )

        if self.console:
            self.console.print(
                f"[green]Sucesso:[/green] Ponte [bold]ID {bridge_id}[/] (porta {bridge.port}) rotacionada para a proxy '[bold]{new_outbound.tag}[/]'"
            )
        
        return True