"""
Componentes de Tabela para a UI.
"""

from typing import List, Dict, Any, Optional
from rich.table import Table
from rich import box
from raxy.ui.console import get_console

def create_table(title: str, columns: List[str]) -> Table:
    """Cria uma tabela padronizada."""
    table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    for col in columns:
        table.add_column(col)
    return table


def show_execution_summary(stats: Dict[str, Any]) -> None:
    """Exibe o resumo de execução em tabela."""
    console = get_console()
    
    table = create_table("📋 Resumo da Execução", ["Métrica", "Valor"])
    table.add_row("Total", str(stats.get("total", 0)))
    table.add_row("Sucesso", f"[green]{stats.get('sucesso', 0)}[/green]")
    table.add_row("Falha", f"[red]{stats.get('falha', 0)}[/red]")
    table.add_row("Pontos", f"[yellow]+{stats.get('pontos_totais', 0)}[/yellow]")
    
    console.print("\n")
    console.print(table)


def show_accounts_table(accounts: List[Dict[str, Any]]) -> None:
    """Exibe lista de contas."""
    table = create_table("Contas Carregadas", ["Email", "Status", "Pontos"])
    for acc in accounts:
        table.add_row(
            acc["email"],
            acc.get("status", "N/A"),
            str(acc.get("pontos", 0))
        )
    get_console().print(table)

def show_failures(failures: List[Dict[str, Any]]) -> None:
    """Exibe tabela de falhas."""
    if not failures:
        return
        
    table = create_table("❌ Contas com Falha", ["Email", "Erro Fatal", "Etapa Falha"])
    
    for f in failures:
        # Extrai primeira etapa com erro se houver
        etapa_erro = "-"
        msg_erro = "-"
        
        if f.get("etapas"):
            for nome, dados in f["etapas"].items():
                if not dados.get("sucesso"):
                    etapa_erro = nome
                    msg_erro = str(dados.get("erro", "Desconhecido"))
                    break
        
        if f.get("erro_fatal"):
            msg_erro = str(f["erro_fatal"])
            
        table.add_row(
            f["email"],
            msg_erro,
            etapa_erro
        )
            
    get_console().print("\n")
    get_console().print(table)
