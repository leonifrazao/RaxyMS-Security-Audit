# raxy_project/cli.py
"""Ponto de entrada da Interface de Linha de Comando (CLI) para o projeto Raxy."""

from __future__ import annotations

from typing import List, Optional, Dict, Any

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

# Updated imports for src/raxy structure
from raxy.infrastructure.config.config import AppConfig, ExecutorConfig, get_config
from raxy.core.domain.accounts import Conta
from raxy.core.domain.proxy import Proxy
from raxy.core.services.executor_service import ExecutorEmLote

from raxy.adapters.repositories.file_account_repository import ArquivoContaRepository
from raxy.adapters.api.supabase_api import SupabaseRepository

from raxy.infrastructure.manager import ProxyManager
from raxy.infrastructure.logging import get_logger

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



# --- Comando Principal: run ---
@app.command(help="[bold green]Executa o processo de farm. Este é o comando principal.[/bold green]")
def run(
    actions: Annotated[
        Optional[List[str]],
        typer.Option("--action", "-a", help="Ação para executar (pode usar várias vezes)."),
    ] = None,
    source: Annotated[
        str,
        typer.Option(help="Origem das contas para execução em lote: 'file' ou 'database'.", case_sensitive=False),
    ] = "file",
    email: Annotated[
        Optional[str],
        typer.Option("-e", "--email", help="Email de uma conta específica para executar (ignora --source).")
    ] = None,
    password: Annotated[
        Optional[str],
        typer.Option("-p", "--password", help="Senha da conta específica (requer --email).")
    ] = None,
    profile_id: Annotated[
        Optional[str],
        typer.Option("--profile-id", help="ID do perfil para a conta específica (opcional, usa email como padrão).")
    ] = None,
    use_proxy: Annotated[
        bool,
        typer.Option("--use-proxy/--no-proxy", help="Ativa ou desativa o uso de proxies para a execução.")
    ] = True,
    proxy_uri: Annotated[
        Optional[str],
        typer.Option("--proxy-uri", help="URI de um proxy específico para usar na execução de conta única.")
    ] = None,
    workers: Annotated[
        Optional[int],
        typer.Option("-w", "--workers", help="Número de execuções paralelas em lote.")
    ] = None,
) -> None:
    """Executa o processo principal de automação com opções de personalização."""

    # --- Configuração do Executor e Injeção de Dependência ---
    # --- Configuração do Executor e Injeção de Dependência ---
    config_params = {}
    if workers:
        config_params['max_workers'] = workers
    
    executor_config = ExecutorConfig(**config_params)
    
    # Cria AppConfig com o ExecutorConfig customizado
    app_config = get_config()
    app_config.executor = executor_config
    
    logger = get_logger()

    # Configuração do ProxyManager
    proxies_list = []
    if use_proxy:
        if proxy_uri:
            proxies_list = [proxy_uri]
        # Se não tiver proxy_uri, o ProxyManager vai carregar das fontes configuradas (se houver)
        # ou podemos passar as fontes do config se necessário.
        # Assumindo que ProxyManager carrega defaults ou é configurado depois.
        # Na implementação original, o container configurava o ProxyService.
        # Vamos assumir que o ProxyManager deve ser instanciado com as configs do app_config se disponível.
        # Por simplicidade, vamos instanciar sem argumentos extras por enquanto, 
        # ou carregar do config se o ProxyManager suportar.
        # O ProxyManager original recebia proxies/sources no init.
        
        # Vamos carregar as fontes do config se existirem
        sources = app_config.proxy.sources if hasattr(app_config, 'proxy') else None
        proxy_manager = ProxyManager(proxies=proxies_list, sources=sources, use_console=True)
    else:
        # Se não usar proxy, instanciamos um ProxyManager vazio que não vai retornar nada
        proxy_manager = ProxyManager(proxies=[], sources=[], use_console=True)
        console.print("[yellow]Executando sem proxies.[/yellow]")

    # Repositório de Contas
    if source.lower() == "database":
        repo = SupabaseRepository(logger=logger)
    else:
        repo = ArquivoContaRepository(app_config.executor.users_file)

    # Executor
    executor = ExecutorEmLote(
        max_workers=executor_config.max_workers,
        logger=logger
    )

    # --- Lógica de Execução ---
    contas_para_executar: list[Conta] = []
    
    # Caso 1: Execução de conta única
    if email:
        if not password:
            console.print("[bold red]❌ A opção --password é obrigatória quando --email é fornecida.[/bold red]")
            raise typer.Exit(code=1)
        
        console.print(f"[bold cyan]🚀 Iniciando execução para conta única: {email}[/bold cyan]")
        id_perfil_final = profile_id or email
        contas_para_executar.append(Conta(email, password, id_perfil_final))
        console.print(f"   - [b]Perfil ID:[/b] {id_perfil_final}")
    
    # Caso 2: Execução em lote (comportamento padrão)
    else:
        console.print("[bold cyan]🚀 Iniciando execução em lote...[/bold cyan]")
        console.print(f"   - [b]Origem das contas:[/b] {source}")
        
        if source.lower() == "database":
            console.print("[yellow]Carregando contas do banco de dados...[/yellow]")
            # repo já é SupabaseRepository aqui
            registros = repo.listar_contas()
            for registro in registros:
                if not isinstance(registro, dict): continue
                db_email = registro.get("email")
                db_senha = registro.get("senha") or registro.get("password") or ""
                if not db_email or not db_senha:
                    logger.aviso("Registro de conta inválido no DB ignorado.", registro=str(registro)[:100])
                    continue
                db_perfil = registro.get("id_perfil") or registro.get("perfil") or db_email
                contas_para_executar.append(Conta(db_email, db_senha, db_perfil))
            if not contas_para_executar:
                console.print("[bold red]❌ Nenhuma conta encontrada no banco de dados.[/bold red]")
                raise typer.Exit(code=1)
        else: # source == 'file'
            try:
                # repo já é ArquivoContaRepository aqui
                contas_para_executar = repo.listar()
                if not contas_para_executar:
                    console.print(f"[bold red]❌ Nenhuma conta encontrada no arquivo de origem.[/bold red]")
                    raise typer.Exit(code=1)
            except FileNotFoundError:
                console.print(f"[bold red]❌ Arquivo de contas não encontrado no caminho configurado.[/bold red]")
                raise typer.Exit(code=1)

    acoes_finais = actions or executor_config.actions
    console.print(f"   - [b]Ações:[/b] {acoes_finais}")
    
    executor.executar(
        contas=contas_para_executar,
        acoes=acoes_finais,
        usar_proxy=use_proxy
    )
    console.print("[bold green]✅ Execução concluída.[/bold green]")


# --- Subcomandos (sem alterações) ---
@accounts_app.command("list-file", help="Lista as contas do arquivo (ex: users.txt).")
def list_file_accounts() -> None:
    """Exibe as contas configuradas no arquivo de texto."""
    app_config = get_config()
    repo = ArquivoContaRepository(app_config.executor.users_file)
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
    logger = get_logger()
    repo = SupabaseRepository(logger=logger)
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
    app_config = get_config()
    sources = app_config.proxy.sources if hasattr(app_config, 'proxy') else None
    proxy_service = ProxyManager(sources=sources, use_console=True)
    console.print("[bold cyan]Iniciando teste de proxies...[/bold cyan]")
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
    app_config = get_config()
    sources = app_config.proxy.sources if hasattr(app_config, 'proxy') else None
    proxy_service = ProxyManager(sources=sources, use_console=True)
    console.print("[bold cyan]Iniciando pontes de proxy...[/bold cyan]")
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
    # Para parar, não precisamos carregar fontes, apenas acessar o gerenciamento de processos
    proxy_service = ProxyManager(use_console=True)
    console.print("[bold yellow]Parando pontes de proxy...[/bold yellow]")
    proxy_service.stop()
    console.print("[bold green]✅ Pontes paradas com sucesso.[/bold green]")


@proxy_app.command("rotate", help="Rotaciona o proxy de uma ponte HTTP ativa.")
def rotate_proxy(
    bridge_id: int = typer.Argument(..., help="O ID da ponte a ser rotacionada."),
) -> None:
    """Troca a proxy de uma ponte específica por outra disponível."""
    app_config = get_config()
    sources = app_config.proxy.sources if hasattr(app_config, 'proxy') else None
    proxy_service = ProxyManager(sources=sources, use_console=True)
    if not proxy_service.get_http_proxy():
        console.print("[yellow]Nenhuma ponte ativa. Iniciando pontes antes de rotacionar...[/yellow]")
        proxy_service.start(auto_test=True, wait=False)
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


@proxy_app.command("clear", help="Limpa o cache de proxies.")
def clear_cache(
    age: Optional[str] = typer.Option(
        None, 
        help="Limpa apenas proxies mais antigos que o especificado (ex: '1S,2D', '12H'). Formato: S=semana, D=dia, H=hora, M=minuto."
    ),
) -> None:
    """Limpa o cache de proxies testados."""
    from pathlib import Path
    
    cache_path = Path(__file__).parent / "raxy" / "proxy" / "proxy_cache.json"
    
    if not cache_path.exists():
        console.print("[yellow]⚠️  Cache não encontrado.[/yellow]")
        return
    
    if age:
        console.print(f"[yellow]⚠️  Limpeza por idade ainda não implementada. Limpando todo o cache...[/yellow]")
    
    try:
        # Remove o arquivo de cache
        cache_path.unlink()
        console.print("[bold green]✅ Cache limpo com sucesso![/bold green]")
        console.print(f"[dim]Arquivo removido: {cache_path}[/dim]")
    except Exception as e:
        console.print(f"[bold red]❌ Erro ao limpar cache: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command(help="[bold blue]Inicia a API REST do Raxy.[/bold blue]")
def api(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host para o servidor."),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Porta para o servidor."),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option("--reload/--no-reload", help="Ativa hot-reload para desenvolvimento."),
    ] = False,
    workers: Annotated[
        int,
        typer.Option("--workers", "-w", help="Número de workers (produção)."),
    ] = 1,
) -> None:
    """Inicia o servidor FastAPI do Raxy."""
    import uvicorn
    
    console.print(f"[bold cyan]🚀 Iniciando Raxy API em http://{host}:{port}[/bold cyan]")
    console.print(f"   - [b]Reload:[/b] {'Ativado' if reload else 'Desativado'}")
    console.print(f"   - [b]Workers:[/b] {workers}")
    console.print("")
    console.print("[dim]Pressione Ctrl+C para encerrar.[/dim]")
    
    uvicorn.run(
        "raxy.adapters.http.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,  # reload não suporta múltiplos workers
    )


if __name__ == "__main__":
    app()