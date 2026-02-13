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
from raxy.models.accounts import Conta
from raxy.interfaces.database import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import (
    IExecutorEmLoteService,
    ILoggingService,
    IProxyService,
)
from raxy.infrastructure.proxy import Proxy
from raxy.infrastructure.database import LocalFileSystem, SQLiteRepository, SupabaseRepository

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
        typer.Option(help="Origem das contas: 'local' (sqlite) ou 'cloud' (supabase).", case_sensitive=False),
    ] = "local",
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
            console.print("[bold red] A opção --password é obrigatória quando --email é fornecida.[/bold red]")
            raise typer.Exit(code=1)
        
        console.print(f"[bold cyan] Iniciando execução para conta única: {email}[/bold cyan]")
        id_perfil_final = profile_id or email
        contas_para_executar.append(Conta(email, password, id_perfil_final))
        console.print(f"   - [b]Perfil ID:[/b] {id_perfil_final}")
    
    # Caso 2: Execução em lote (comportamento padrão)
    else:
        console.print("[bold cyan] Iniciando execução em lote...[/bold cyan]")
        console.print(f"   - [b]Origem das contas:[/b] {source}")
        
        # Seleciona repositório baseado na fonte selectionada
        if source.lower() in ("cloud", "supabase", "database"):
             console.print("[yellow]Usando Supabase (Cloud)...[/yellow]")
             # Container deve ser configurado para usar Supabase se necessário, ou instanciamos aqui
             # Idealmente, o container já resolve isso se a config estiver certa, mas aqui forçamos
             # Para simplificar, vamos assumir que o default do container será SQLite, e override se cloud
             try:
                 repo = container.database_repository() # Tenta pegar o do container, que pode ser None se config ausente
                 if not repo:
                     # Se não configurado no container, tenta instanciar direto
                     from raxy.infrastructure.database import SupabaseRepository
                     repo = SupabaseRepository()
             except Exception as e:
                 console.print(f"[bold red] Erro ao inicializar repositório Cloud: {e}[/bold red]")
                 raise typer.Exit(code=1)
        else:
             # Default: Local SQLite
             console.print("[yellow] Usando SQLite (Local)...[/yellow]")
             repo = container.conta_repository() # Deve retornar SQLiteRepository

        try:
            # Lista contas usando interface unificada IContaRepository
            contas_para_executar = repo.listar()
            if not contas_para_executar:
                console.print("[bold red] Nenhuma conta encontrada no banco de dados. Use 'raxy accounts import' para adicionar.[/bold red]")
                raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[bold red] Erro ao acessar banco de dados: {e}[/bold red]")
            raise typer.Exit(code=1)

    acoes_finais = actions or app_config.executor.actions
    console.print(f"   - [b]Ações:[/b] {acoes_finais}")
    
    executor.executar(acoes=acoes_finais, contas=contas_para_executar)
    console.print("[bold green] Execução concluída.[/bold green]")


# --- Subcomandos (sem alterações) ---
@accounts_app.command("import", help="Importa contas de um arquivo de texto para o banco de dados.")
def import_accounts(
    file_path: str = typer.Argument(..., help="Caminho do arquivo users.txt (formato email:senha)."),
    target: str = typer.Option("local", help="Destino: 'local' (sqlite) ou 'cloud' (supabase)."),
) -> None:
    """Carrega contas do arquivo e salva no banco de dados selecionado."""
    console.print(f"[bold cyan]Importando contas de {file_path} para {target}...[/bold cyan]")
    
    fs = LocalFileSystem()
    try:
        contas = fs.import_accounts_from_file(file_path)
    except Exception as e:
        console.print(f"[bold red] Erro ao ler arquivo: {e}[/bold red]")
        raise typer.Exit(code=1)

    if not contas:
        console.print("[yellow]Nenhuma conta válida encontrada no arquivo.[/yellow]")
        return

    # Seleciona repositório
    if target.lower() in ("cloud", "supabase"):
        from raxy.infrastructure.database import SupabaseRepository
        repo = SupabaseRepository()
    else:
        from raxy.infrastructure.database import SQLiteRepository
        # Instancia repository sqlite padrão
        repo = SQLiteRepository()

    # Salva
    sucesso = 0
    with typer.progressbar(contas, label="Salvando contas") as progress:
        for conta in progress:
            try:
                repo.salvar(conta)
                sucesso += 1
            except Exception as e:
                console.print(f"[red]Falha ao salvar {conta.email}: {e}[/red]")

    console.print(f"[bold green]Importação concluída. {sucesso}/{len(contas)} contas salvas.[/bold green]")


@accounts_app.command("list", help="Lista as contas do banco de dados.")
def list_accounts(
    source: str = typer.Option("local", help="Fonte: 'local' (sqlite) ou 'cloud' (supabase).")
) -> None:
    """Exibe as contas configuradas no banco de dados."""
    
    if source.lower() in ("cloud", "supabase"):
        from raxy.infrastructure.database import SupabaseRepository
        repo = SupabaseRepository()
        title = "Contas Supabase (Cloud)"
    else:
        # Pega do container ou instancia direito
        container = get_container()
        repo = container.conta_repository()
        title = "Contas SQLite (Local)"

    try:
        contas = repo.listar_contas()
    except Exception as e:
        console.print(f"[bold red] Erro ao acessar banco: {e}[/bold red]")
        return

    if not contas:
        console.print(f"[yellow] Nenhuma conta encontrada em {source}.[/yellow]")
        return

    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Email")
    table.add_column("ID do Perfil")
    table.add_column("Proxy")
    table.add_column("Pontos")
    table.add_column("Última Farm")

    for conta in contas:
        # Adapter para lidar com dict ou objeto dependendo da implementação
        # listar_contas retorna lista de dicts no sqlite, mas vamos garantir
        if hasattr(conta, "to_dict"):
             dados = conta.to_dict()
        elif isinstance(conta, dict):
             dados = conta
        else:
             continue

        table.add_row(
            str(dados.get("email", "-")),
            str(dados.get("id_perfil", dados.get("perfil", "-"))),
            str(dados.get("proxy", "-")),
            str(dados.get("pontos", "-")),
            str(dados.get("ultima_farm", "-")),
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
    console.print("[bold green] Teste de proxies concluído.[/bold green]")


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
    console.print("[bold yellow] Parando pontes de proxy...[/bold yellow]")
    proxy_service.stop()
    console.print("[bold green] Pontes paradas com sucesso.[/bold green]")


@proxy_app.command("rotate", help="Rotaciona o proxy de uma ponte HTTP ativa.")
def rotate_proxy(
    bridge_id: int = typer.Argument(..., help="O ID da ponte a ser rotacionada."),
) -> None:
    """Troca a proxy de uma ponte específica por outra disponível."""
    container = get_container()
    proxy_service = container.proxy_service()
    if not proxy_service.get_http_proxy():
        console.print("[yellow] Nenhuma ponte ativa. Iniciando pontes antes de rotacionar...")
        proxy_service.start(auto_test=True, wait=False)
        if not proxy_service.get_http_proxy():
            console.print("[bold red] Falha ao iniciar pontes. Não é possível rotacionar.[/bold red]")
            raise typer.Exit(code=1)

    console.print(f"[bold cyan]Rotacionando proxy da ponte ID {bridge_id}...[/bold cyan]")
    success = proxy_service.rotate_proxy(bridge_id)
    if not success:
        console.print(f"[bold red] Falha ao rotacionar a ponte {bridge_id}.[/bold red]")
        raise typer.Exit(code=1)
    else:
        console.print("[bold green] Proxy rotacionado com sucesso![/bold green]")
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
        console.print("[yellow] Cache não encontrado.[/yellow]")
        return
    
    if age:
        console.print(f"[yellow] Limpeza por idade ainda não implementada. Limpando todo o cache...[/yellow]")
    
    try:
        # Remove o arquivo de cache
        cache_path.unlink()
        console.print("[bold green] Cache limpo com sucesso![/bold green]")
        console.print(f"[dim]Arquivo removido: {cache_path}[/dim]")
    except Exception as e:
        console.print(f"[bold red] Erro ao limpar cache: {e}[/bold red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()