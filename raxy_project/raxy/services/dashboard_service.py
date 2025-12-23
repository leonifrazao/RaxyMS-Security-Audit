"""
Serviço de Dashboard em Tempo Real.

Responsável por visualizar o status da execução em lote usando a biblioteca Rich.
"""

from __future__ import annotations

import time
from typing import Dict, Any, List, Optional
from threading import Lock

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskID
from rich.layout import Layout
from rich.panel import Panel
from rich import box

from raxy.services.base_service import BaseService
from raxy.interfaces.services import ILoggingService

class LiveDashboardService(BaseService):
    """
    Serviço que gerencia o dashboard em tempo real no terminal.
    """
    
    def __init__(self, logger: Optional[ILoggingService] = None, enabled: bool = True):
        super().__init__(logger)
        self.enabled = enabled
        self.console = Console()
        self._lock = Lock()
        
        # State
        self.total_accounts = 0
        self.results = {"success": 0, "fail": 0, "total": 0}
        self.worker_status: Dict[str, Dict[str, str]] = {} # map[worker_id] -> {email, status}
        self.progress: Optional[Progress] = None
        self.task_id: Optional[TaskID] = None
        self.live: Optional[Live] = None
        self.layout = Layout()
        self.task_id: Optional[TaskID] = None
        self.live: Optional[Live] = None
        self.layout = Layout()
        self.started = False
        self.global_status: str = "" # Status global (ex: Buscando proxies...)
        
        # Logs capturados para debug visual (opcional)
        self.recent_logs: List[str] = []

    def start(self, total_accounts: int) -> None:
        """Inicia o dashboard."""
        if not self.enabled:
            return
            
        self.total_accounts = total_accounts
        self.started = True
        
        # Initialize Progress
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("{task.completed}/{task.total}"),
        )
        self.task_id = self.progress.add_task("[cyan]Processando contas...", total=total_accounts)
        
        # Setup Layout
        self._setup_layout()
        
        # Create Live instance
        self.live = Live(
            self._generate_renderable(),
            refresh_per_second=4,
            console=self.console,
            screen=False # Não limpar tela inteira, apenas a área do live
        )
        
        # Silencia logs de console para não interferir na UI
        if self.logger:
            self.logger.mute_console()
            
        self.live.start()

    def stop(self) -> None:
        """Para o dashboard."""
        if self.live:
            self.live.stop()
            self.live = None
            
        # Restaura logs de console
        if self.logger:
            self.logger.unmute_console()
            
        self.started = False

    def update_worker(self, worker_id: str, email: str, status: str) -> None:
        """Atualiza o status de um worker."""
        if not self.enabled or not self.started:
            return
            
        with self._lock:

            self.worker_status[worker_id] = {
                "email": email,
                "status": status,
                "timestamp": time.time()
            }
        self.update()
            
    def set_global_status(self, status: str) -> None:
        """Define status global da aplicação."""
        if not self.enabled:
            return
        self.global_status = status
        self.update()

    def worker_done(self, worker_id: str) -> None:
        """Remove worker da tabela ativa."""
        if not self.enabled or not self.started:
            return
            
        with self._lock:
            if worker_id in self.worker_status:
                del self.worker_status[worker_id]
        self.update()

    def increment_success(self) -> None:
        """Incrementa contador de sucesso."""
        if not self.enabled:
            return
        with self._lock:
            self.results["success"] += 1
            self.results["total"] += 1
            if self.progress and self.task_id is not None:
                self.progress.advance(self.task_id)
        self.update()

    def increment_failure(self) -> None:
        """Incrementa contador de falha."""
        if not self.enabled:
            return
        with self._lock:
            self.results["fail"] += 1
            self.results["total"] += 1
            if self.progress and self.task_id is not None:
                self.progress.advance(self.task_id)
        self.update()

    def update(self) -> None:
        """Força atualização da renderização."""
        if self.live:
            self.live.update(self._generate_renderable())

    def _setup_layout(self) -> None:
        """Configura o layout inicial."""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3),
        )

    def _generate_renderable(self) -> Layout:
        """Gera o objeto renderizável atualizado."""
        # Header: Progress Bar + Global Status
        header_grid = Table.grid(expand=True)
        header_grid.add_column(ratio=1)
        header_grid.add_row(self.progress)
        
        if self.global_status:
            header_grid.add_row(f"[bold yellow]{self.global_status}[/bold yellow]")
            
        self.layout["header"].update(
            Panel(header_grid, title="Progresso Global", border_style="cyan", padding=(0, 1))
        )
        
        # Main: Worker Table
        table = Table(title="Workers Ativos", expand=True, box=box.SIMPLE_HEAD)
        table.add_column("Worker", style="magenta", width=10)
        table.add_column("Conta", style="cyan")
        table.add_column("Status", style="yellow")
        
        # Sort by worker ID usually looks better
        with self._lock:
            sorted_workers = sorted(self.worker_status.items())
            for wid, data in sorted_workers:
                table.add_row(str(wid), data["email"], data["status"])
            
            # Placeholder if empty
            if not sorted_workers:
                table.add_row("-", "Aguardando tasks...", "-")

        self.layout["main"].update(
            Panel(table, title="Monitoramento de Threads", border_style="blue")
        )
        
        # Footer: Summary
        summary_grid = Table.grid(expand=True)
        summary_grid.add_column(justify="center", ratio=1)
        summary_grid.add_column(justify="center", ratio=1)
        summary_grid.add_column(justify="center", ratio=1)
        
        with self._lock:
            s = self.results["success"]
            f = self.results["fail"]
            t = self.results["total"]
            
        summary_grid.add_row(
            f"[green]✅ Sucessos: {s}[/green]",
            f"[red]❌ Falhas: {f}[/red]",
            f"[bold]📊 Total Processado: {t}/{self.total_accounts}[/bold]"
        )
        
        self.layout["footer"].update(
            Panel(summary_grid, title="Resumo Parcial", border_style="green")
        )
        
        return self.layout
