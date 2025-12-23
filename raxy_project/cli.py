# raxy_project/cli.py
"""Ponto de entrada da Interface de Linha de Comando (CLI) para o projeto Raxy."""

from __future__ import annotations

from typing import List, Optional, Dict, Any

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from dependency_injector import providers

from raxy.container import ApplicationContainer, get_container
from raxy.core.config import AppConfig, ExecutorConfig, get_config
from raxy.domain.accounts import Conta
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import (
    IExecutorEmLoteService,
    ILoggingService,
    IProxyService,
)
from raxy.infrastructure.proxy import Proxy

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

# --- Classe Auxiliar para Desativar Proxy ---
class DummyProxyService(IProxyService):
    """Implementação de IProxyService que não faz nada, efetivamente desativando os proxies."""
    def add_sources(self, sources: List[str]) -> int: return 0
    def add_proxies(self, proxies: List[str]) -> int: return 0
    def test(self, **kwargs) -> List[Dict]: return []
    def start(self, **kwargs) -> List[Dict]:
        console.print("[yellow]Executando sem proxies.[/yellow]")
        return []
    def stop(self) -> None: pass
    def get_http_proxy(self) -> List[Dict]: return []
    def rotate_proxy(self, bridge_id: int) -> bool: return False

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
    app_config = get_config()
    
    # Atualiza configuração com parâmetros da CLI se fornecidos
    if workers:
        app_config.executor.max_workers = workers
    
    # Cria um container customizado para esta execução
    container = ApplicationContainer()
    container.config.override(providers.Singleton(lambda: app_config))
    
    # Sobrescreve o serviço de proxy se necessário
    if not use_proxy:
        container.proxy_service.override(providers.Object(DummyProxyService()))
    elif email and proxy_uri: # Apenas para conta única, usa o proxy especificado
        single_proxy_service = Proxy(proxies=[proxy_uri], use_console=True)
        container.proxy_service.override(providers.Object(single_proxy_service))

    executor = container.executor_service()
    logger = container.logger()
    
    # Sincroniza nível de log com configuração
    if app_config.debug:
        logger.set_level("DEBUG")
        logger.debug("Nível de log ajustado para DEBUG via CLI/Config")

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
            db_repo = container.database_repository()
            registros = db_repo.listar_contas()
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
                file_repo = container.conta_repository()
                contas_para_executar = file_repo.listar()
                if not contas_para_executar:
                    console.print(f"[bold red]❌ Nenhuma conta encontrada no arquivo de origem.[/bold red]")
                    raise typer.Exit(code=1)
            except FileNotFoundError:
                console.print(f"[bold red]❌ Arquivo de contas não encontrado no caminho configurado.[/bold red]")
                raise typer.Exit(code=1)

    acoes_finais = actions or app_config.executor.actions
    console.print(f"   - [b]Ações:[/b] {acoes_finais}")
    
    executor.executar(acoes=acoes_finais, contas=contas_para_executar)
    console.print("[bold green]✅ Execução concluída.[/bold green]")


# --- Subcomandos (sem alterações) ---
@accounts_app.command("list-file", help="Lista as contas do arquivo (ex: users.txt).")
def list_file_accounts() -> None:
    """Exibe as contas configuradas no arquivo de texto."""
    container = get_container()
    repo = container.conta_repository()
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
    container = get_container()
    repo = container.database_repository()
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
    container = get_container()
    proxy_service = container.proxy_service()
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
    container = get_container()
    proxy_service = container.proxy_service()
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
    container = get_container()
    proxy_service = container.proxy_service()
    console.print("[bold yellow]Parando pontes de proxy...[/bold yellow]")
    proxy_service.stop()
    console.print("[bold green]✅ Pontes paradas com sucesso.[/bold green]")


@proxy_app.command("rotate", help="Rotaciona o proxy de uma ponte HTTP ativa.")
def rotate_proxy(
    bridge_id: int = typer.Argument(..., help="O ID da ponte a ser rotacionada."),
) -> None:
    """Troca a proxy de uma ponte específica por outra disponível."""
    container = get_container()
    proxy_service = container.proxy_service()
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
    
    cache_path = Path(__file__).parent / "raxy" / "infrastructure" / "proxy" / "proxy_cache.json"
    
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


if __name__ == "__main__":
    app()