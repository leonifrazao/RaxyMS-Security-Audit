# raxy_project/cli.py
"""Ponto de entrada da Interface de Linha de Comando (CLI) para o projeto Raxy."""

from __future__ import annotations

from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from raxy.container import create_injector
from raxy.domain.accounts import Conta
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import (
    IExecutorEmLoteService,
    ILoggingService,
    IProxyService,
)

# --- Configuração da Aplicação CLI ---
app = typer.Typer(
    name="raxy",
    help="CLI para gerenciar e executar as automações do Raxy Project.",
    add_completion=False,
    rich_markup_mode="rich",
)
proxy_app = typer.Typer(name="proxy", help="Gerenciar e testar proxies.")
accounts_app = typer.Typer(name="accounts", help="Listar contas configuradas.")
app.add_typer(proxy_app, no_args_is_help=True)
app.add_typer(accounts_app, no_args_is_help=True)

# --- Instâncias Globais ---
console = Console()
injector = create_injector()


# --- Comando Principal: run ---
@app.command(help="[bold green]Executa o processo de farm em lote. Este é o comando principal.[/bold green]")
def run(
    actions: Annotated[
        Optional[List[str]],
        typer.Option(
            "--action",
            "-a",
            help="Ação para executar (pode usar várias vezes). Padrão: login, rewards, solicitacoes.",
        ),
    ] = None,
    source: Annotated[
        str,
        typer.Option(
            help="Origem das contas: 'file' ou 'database'.",
            case_sensitive=False,
        ),
    ] = "file",
) -> None:
    """Executa o processo principal de automação."""
    executor = injector.get(IExecutorEmLoteService)
    logger = injector.get(ILoggingService)

    console.print("[bold cyan]🚀 Iniciando execução do Raxy...[/bold cyan]")
    console.print(f"   - [b]Ações:[/b] {actions or ['padrão']}")
    console.print(f"   - [b]Origem das contas:[/b] {source}")

    contas_para_executar: list[Conta] = []
    if source.lower() == "database":
        console.print("[yellow]Carregando contas do banco de dados...[/yellow]")
        db_repo = injector.get(IDatabaseRepository)
        registros = db_repo.listar_contas()
        for registro in registros:
            if not isinstance(registro, dict):
                continue
            email = registro.get("email")
            senha = registro.get("senha") or registro.get("password") or ""
            if not email or not senha:
                logger.aviso("Registro de conta inválido no DB ignorado.", registro=str(registro)[:100])
                continue
            perfil = registro.get("id_perfil") or registro.get("perfil") or email
            proxy = registro.get("proxy") or registro.get("proxy_uri") or ""
            contas_para_executar.append(Conta(email, senha, perfil, proxy))
        if not contas_para_executar:
            console.print("[bold red]❌ Nenhuma conta encontrada no banco de dados.[/bold red]")
            raise typer.Exit(code=1)

    # Se a fonte for 'file' ou qualquer outra, o executor usará o repositório padrão (ArquivoContaRepository)
    # se `contas_para_executar` permanecer vazio.
    executor.executar(acoes=actions, contas=contas_para_executar or None)
    console.print("[bold green]✅ Execução concluída.[/bold green]")


# --- Subcomandos: accounts ---
@accounts_app.command("list-file", help="Lista as contas do arquivo (ex: users.txt).")
def list_file_accounts() -> None:
    """Exibe as contas configuradas no arquivo de texto."""
    repo = injector.get(IContaRepository)
    try:
        contas = repo.listar()
        if not contas:
            console.print("[yellow]Nenhuma conta encontrada no arquivo.[/yellow]")
            return

        table = Table(title="Contas do Arquivo", show_header=True, header_style="bold magenta")
        table.add_column("Email")
        table.add_column("ID do Perfil")
        for conta in contas:
            table.add_row(conta.email, conta.id_perfil)
        console.print(table)
    except FileNotFoundError:
        console.print("[bold red]❌ Arquivo de contas não encontrado.[/bold red]")
        raise typer.Exit(code=1)


@accounts_app.command("list-db", help="Lista as contas do banco de dados.")
def list_db_accounts() -> None:
    """Exibe as contas configuradas no banco de dados."""
    repo = injector.get(IDatabaseRepository)
    contas = repo.listar_contas()

    if not contas:
        console.print("[yellow]Nenhuma conta encontrada no banco de dados.[/yellow]")
        return

    table = Table(title="Contas do Banco de Dados", show_header=True, header_style="bold magenta")
    table.add_column("Email")
    table.add_column("ID do Perfil")
    table.add_column("Proxy")
    table.add_column("Pontos")
    table.add_column("Última Farm")

    for conta in contas:
        table.add_row(
            str(conta.get("email", "-")),
            str(conta.get("id_perfil", conta.get("perfil", "-"))),
            str(conta.get("proxy", "-")),
            str(conta.get("pontos", "-")),
            str(conta.get("ultima_farm", "-")),
        )
    console.print(table)


# --- Subcomandos: proxy ---
@proxy_app.command("test", help="Testa a conectividade dos proxies.")
def test_proxies(
    threads: int = typer.Option(10, help="Número de workers para os testes."),
    country: Optional[str] = typer.Option(None, help="Código do país para filtrar (ex: US, BR)."),
    timeout: float = typer.Option(10.0, help="Timeout em segundos para cada teste."),
    force: bool = typer.Option(False, "--force", help="Força o re-teste, ignorando o cache."),
    find_first: Optional[int] = typer.Option(
        None, "--find-first", help="Para de testar após encontrar N proxies funcionais."
    ),
) -> None:
    """Executa o teste de proxies e exibe um relatório."""
    proxy_service = injector.get(IProxyService)
    console.print("[bold cyan]Iniciando teste de proxies...[/bold cyan]")
    # O método `test` já usa `rich` para imprimir a saída quando `verbose=True`
    proxy_service.test(
        threads=threads,
        country=country,
        timeout=timeout,
        force=force,
        find_first=find_first,
        verbose=True,
    )
    console.print("[bold green]✅ Teste de proxies concluído.[/bold green]")


@proxy_app.command("start", help="Inicia as pontes de proxy HTTP e aguarda.")
def start_proxies(
    amounts: Optional[int] = typer.Option(None, help="Número máximo de pontes a serem iniciadas."),
    country: Optional[str] = typer.Option(None, help="Código do país para filtrar (ex: US, BR)."),
    find_first: Optional[int] = typer.Option(
        None, "--find-first", help="Para o teste automático após encontrar N proxies."
    ),
) -> None:
    """Inicia os proxies e mantém o processo em execução."""
    proxy_service = injector.get(IProxyService)
    console.print("[bold cyan]Iniciando pontes de proxy...[/bold cyan]")
    # `wait=True` faz o CLI aguardar até ser interrompido (Ctrl+C)
    proxy_service.start(
        amounts=amounts,
        country=country,
        auto_test=True,
        wait=True,
        find_first=find_first,
    )


@proxy_app.command("stop", help="Para todas as pontes de proxy ativas.")
def stop_proxies() -> None:
    """Para os processos de proxy em background."""
    proxy_service = injector.get(IProxyService)
    console.print("[bold yellow]Parando pontes de proxy...[/bold yellow]")
    proxy_service.stop()
    console.print("[bold green]✅ Pontes paradas com sucesso.[/bold green]")


@proxy_app.command("rotate", help="Rotaciona o proxy de uma ponte HTTP ativa.")
def rotate_proxy(
    bridge_id: int = typer.Argument(..., help="O ID da ponte a ser rotacionada."),
) -> None:
    """Troca a proxy de uma ponte específica por outra disponível."""
    proxy_service = injector.get(IProxyService)
    # Inicia o serviço para que as pontes existam antes de rotacionar
    if not proxy_service.get_http_proxy():
        console.print("[yellow]Nenhuma ponte ativa. Iniciando pontes antes de rotacionar...[/yellow]")
        proxy_service.start(auto_test=True, wait=False)  # Inicia em background
        if not proxy_service.get_http_proxy():
            console.print("[bold red]❌ Falha ao iniciar pontes. Não é possível rotacionar.[/bold red]")
            raise typer.Exit(code=1)

    console.print(f"[bold cyan]Rotacionando proxy da ponte ID {bridge_id}...[/bold cyan]")
    success = proxy_service.rotate_proxy(bridge_id)
    if not success:
        console.print(f"[bold red]❌ Falha ao rotacionar a ponte {bridge_id}.[/bold red]")
        raise typer.Exit(code=1)
    else:
        console.print("[bold green]✅ Proxy rotacionado com sucesso![/bold green]")
        console.print(proxy_service.get_http_proxy())


if __name__ == "__main__":
    app()