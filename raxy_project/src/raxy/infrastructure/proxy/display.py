# -*- coding: utf-8 -*-
"""
Módulo de exibição Rich para o gerenciador de proxies.

Fornece formatação visual para tabelas de status, progresso de
testes e resumos usando a biblioteca Rich.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from raxy.infrastructure.proxy.utils import format_destination

if TYPE_CHECKING:
    from rich.console import Console
    from rich.table import Table

# Tenta importar Rich, mas funciona sem ele
try:
    from rich.console import Console as RichConsole
    from rich.table import Table as RichTable
    from rich.text import Text as RichText
    RICH_AVAILABLE = True
except ImportError:
    RichConsole = None  # type: ignore
    RichTable = None  # type: ignore
    RichText = None  # type: ignore
    RICH_AVAILABLE = False


class ProxyDisplayManager:
    """
    Gerencia a exibição de informações de proxy no console.
    
    Usa Rich para formatação colorida quando disponível, ou
    fallback para texto simples.
    
    Attributes:
        console: Instância Rich Console (ou None)
        enabled: Se a exibição está habilitada
    """
    
    # Estilos para cada status de proxy
    STATUS_STYLES: Dict[str, str] = {
        "AGUARDANDO": "dim",
        "TESTANDO": "yellow",
        "OK": "bold green",
        "ERRO": "bold red",
        "FILTRADO": "cyan",
    }
    
    def __init__(self, *, enabled: bool = True) -> None:
        """
        Inicializa o gerenciador de exibição.
        
        Args:
            enabled: Se deve usar Rich para exibição
        """
        self.enabled = enabled and RICH_AVAILABLE
        self.console: Optional["Console"] = RichConsole() if self.enabled else None
    
    def print(self, message: str) -> None:
        """
        Imprime mensagem formatada.
        
        Args:
            message: Texto com markup Rich
        """
        if self.console:
            self.console.print(message)
        elif self.enabled:
            # Remove markup Rich para fallback
            import re
            clean = re.sub(r'\[/?[^\]]+\]', '', message)
            print(clean)
    
    def rule(self, title: str) -> None:
        """
        Exibe uma linha divisória com título.
        
        Args:
            title: Título da seção
        """
        if self.console:
            self.console.rule(title)
        else:
            print(f"\n{'=' * 20} {title} {'=' * 20}")
    
    def emit_test_progress(
        self, 
        entry: Dict[str, Any], 
        count: int, 
        total: int
    ) -> None:
        """
        Exibe progresso de um teste individual.
        
        Args:
            entry: Dados da proxy testada
            count: Número atual
            total: Total de proxies
        """
        if not self.enabled:
            return
        
        destino = format_destination(entry.get("host"), entry.get("port"))
        ping_preview = entry.get("ping")
        ping_fmt = f"{ping_preview:.1f} ms" if isinstance(ping_preview, (int, float)) else "-"
        
        status = entry.get("status", "?")
        status_fmt = {
            "OK": "[bold green]OK[/]",
            "ERRO": "[bold red]ERRO[/]",
            "TESTANDO": "[yellow]TESTANDO[/]",
            "AGUARDANDO": "[dim]AGUARDANDO[/]",
            "FILTRADO": "[cyan]FILTRADO[/]",
        }.get(status, status)
        
        cache_note = " [dim](cache)[/]" if entry.get("cached") else ""
        display_country = entry.get("proxy_country") or entry.get("country") or "-"
        
        self.print(
            f"[{count}/{total}] {status_fmt}{cache_note} [bold]{entry.get('tag', '-')}[/] -> "
            f"{destino} | IP: {entry.get('ip') or '-'} | "
            f"País: {display_country} | Ping: {ping_fmt}"
        )
        
        # Mostra diferença entre servidor e saída
        if entry.get("proxy_ip") and entry.get("proxy_ip") != entry.get("ip"):
            original_country = entry.get("country", "-")
            self.print(
                f"    [dim]País do Servidor: {original_country} -> "
                f"País de Saída: {entry.get('proxy_country', '-')}[/]"
            )
        
        if entry.get("error"):
            self.print(f"    [dim]Motivo: {entry['error']}[/]")
    
    def render_test_summary(
        self, 
        entries: List[Dict[str, Any]], 
        country_filter: Optional[str]
    ) -> None:
        """
        Exibe relatório completo de resultados de teste.
        
        Args:
            entries: Lista de todas as proxies testadas
            country_filter: Filtro de país aplicado (ou None)
        """
        if not self.enabled or not self.console:
            return
        
        ok_entries = [e for e in entries if e.get("status") == "OK"]
        
        if country_filter:
            table_entries = [e for e in ok_entries if e.get("country_match")]
        else:
            table_entries = ok_entries

        self.print("")
        self.rule("Proxies Funcionais")
        
        if table_entries:
            table = self._render_test_table(table_entries)
            self.console.print(table)
        else:
            msg = "[yellow]Nenhuma proxy funcional encontrada.[/yellow]"
            if country_filter:
                msg = f"[yellow]Nenhuma proxy funcional corresponde ao filtro de país '{country_filter}'.[/yellow]"
            self.print(msg)

        # Estatísticas
        success = sum(1 for e in entries if e.get("status") == "OK")
        fail = sum(1 for e in entries if e.get("status") == "ERRO")
        filtered = sum(1 for e in entries if e.get("status") == "FILTRADO")

        self.print("")
        self.rule("Resumo do Teste")
        
        summary_parts = [
            f"[bold cyan]Total:[/] {len(entries)}",
            f"[bold green]Sucesso:[/] {success}",
            f"[bold red]Falhas:[/] {fail}",
        ]
        if filtered:
            summary_parts.append(f"[cyan]Filtradas:[/] {filtered}")
        
        self.print("    ".join(summary_parts))

        # Detalhes de falhas
        failed_entries = [
            e for e in entries
            if e.get("status") == "ERRO" and e.get("error")
        ]
        
        if failed_entries:
            self.print("")
            self.print("[bold red]Detalhes das falhas:[/]")
            for entry in failed_entries[:10]:
                self.print(f" - [bold]{entry.get('tag') or '-'}[/]: {entry['error']}")
            if len(failed_entries) > 10:
                self.print(f"  [dim]... e mais {len(failed_entries) - 10} outras falhas.[/dim]")
    
    def _render_test_table(self, entries: List[Dict[str, Any]]) -> "Table":
        """
        Gera uma tabela Rich com resultados dos testes.
        
        Args:
            entries: Proxies funcionais para exibir
            
        Returns:
            Table Rich formatada
        """
        if not RICH_AVAILABLE or RichTable is None:
            raise RuntimeError("render_test_table requer a biblioteca 'rich'.")
        
        # Ordena por ping
        entries = sorted(entries, key=lambda e: e.get("ping") or float('inf'))

        table = RichTable(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Tag", no_wrap=True, max_width=30)
        table.add_column("Destino", overflow="fold")
        table.add_column("IP Real (Saída)", no_wrap=True)
        table.add_column("País (Saída)", no_wrap=True)
        table.add_column("Ping", justify="right", no_wrap=True)
        
        for entry in entries:
            status = entry.get("status", "-")
            style = self.STATUS_STYLES.get(status, "white")
            status_cell = RichText(status, style=style) if RichText else status
            
            destino = format_destination(entry.get("host"), entry.get("port"))
            ping = entry.get("ping")
            ping_str = f"{ping:.1f} ms" if isinstance(ping, (int, float)) else "-"
            
            display_ip = entry.get("proxy_ip") or entry.get("ip") or "-"
            display_country = entry.get("proxy_country") or entry.get("country") or "-"
            
            table.add_row(
                status_cell,
                entry.get("tag") or "-",
                destino,
                display_ip,
                display_country,
                ping_str,
            )
        
        return table
    
    def show_bridges(
        self, 
        bridges_display: List[tuple],
        country_filter: Optional[str]
    ) -> None:
        """
        Exibe lista de pontes HTTP ativas.
        
        Args:
            bridges_display: Lista de (bridge, ping) tuples
            country_filter: Filtro de país aplicado
        """
        if not self.enabled:
            return
        
        self.print("")
        title = f"Pontes HTTP ativas{f' - País: {country_filter}' if country_filter else ''} - Ordenadas por Ping"
        self.rule(title)
        
        for idx, (bridge, ping) in enumerate(bridges_display):
            ping_str = f"{ping:6.1f}ms" if ping != float('inf') else "     -     "
            self.print(
                f"[bold cyan]ID {idx:<2}[/] http://127.0.0.1:{bridge.port}  ->  [{ping_str}]"
            )
        
        self.print("")
        self.print("Pressione Ctrl+C para encerrar todas as pontes.")


__all__ = ["ProxyDisplayManager", "RICH_AVAILABLE"]
