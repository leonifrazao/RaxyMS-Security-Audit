# raxy_project/cli.py
"""Ponto de entrada da Interface de Linha de Comando (CLI) para o projeto Raxy."""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pathlib import Path

import typer
from rich.console import Console
from typing_extensions import Annotated

# === NOVOS IMPORTS ===
from raxy.config import get_config, AppConfig, ExecutorConfig
from raxy.core.models import Conta, Proxy
from raxy.services.executor import BatchExecutor
from raxy.adapters.repositories.file_account_repository import FileAccountRepository
from raxy.adapters.api.supabase_api import SupabaseAccountRepository
from raxy.adapters.repositories.session_state_repository import InMemorySessionStateRepository
from raxy.adapters.api.mail_tm_api import MailTm

# Usamos UI unificada
from dataclasses import asdict
from raxy.ui.console import get_console, print_info, print_error, print_success, print_warning
from raxy.ui.tables import show_execution_summary, show_accounts_table, show_failures

# Mantemos imports de infra legado/refatorado se necessário
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


# --- Comando Principal: run ---
@app.command(help="[bold green]Executa o processo de farm.[/bold green]")
def run(
    actions: Annotated[
        Optional[List[str]],
        typer.Option("--action", "-a", help="Ação para executar."),
    ] = None,
    source: Annotated[
        str,
        typer.Option(help="Origem das contas: 'file' ou 'database'.", case_sensitive=False),
    ] = "file",
    email: Annotated[
        Optional[str],
        typer.Option("-e", "--email", help="Email de uma conta específica.")
    ] = None,
    password: Annotated[
        Optional[str],
        typer.Option("-p", "--password", help="Senha da conta (requer --email).")
    ] = None,
    profile_id: Annotated[
        Optional[str],
        typer.Option("--profile-id", help="ID do perfil.")
    ] = None,
    use_proxy: Annotated[
        bool,
        typer.Option("--use-proxy/--no-proxy", help="Ativa/desativa proxy.")
    ] = True,
    proxy_uri: Annotated[
        Optional[str],
        typer.Option("--proxy-uri", help="URI de proxy específico.")
    ] = None,
    workers: Annotated[
        Optional[int],
        typer.Option("-w", "--workers", help="Número de execuções paralelas.")
    ] = None,
) -> None:
    """Executa o processo principal de automação."""
    logger = get_logger()
    console = get_console()

    # 1. Carrega Configuração
    app_config = get_config()
    
    # Overrides via CLI
    if workers:
        app_config.executor.max_workers = workers
    
    # 2. Configura Repositório de Contas
    if source.lower() == "database":
        repo = SupabaseAccountRepository(logger=logger)
    else:
        # Resolve caminho do arquivo de usuários
        users_file = app_config.executor.users_file
        # Se não for absoluto, assume relativo ao root do projeto ou data_dir
        # Por simplicidade, usamos Path direto, mas config loader poderia resolver
        repo = FileAccountRepository(users_file)

    # 3. Configura Proxies
    proxies_list = []
    proxy_manager = None
    
    if use_proxy:
        if proxy_uri:
            # Proxy manual único
            proxies_list = [Proxy(id="manual", url=proxy_uri)]
        else:
            # Proxy Manager (Legado/Refatorado)
            # Idealmente, o ProxyManager deveria retornar lista de objetos Proxy
            sources = app_config.proxy.sources
            print_info("Iniciando Proxy Manager...")
            proxy_manager = ProxyManager(
                sources=sources, 
                use_console=app_config.proxy.use_console,
                country=app_config.proxy.country
            )
            # Inicia bridges e pega proxies
            raw_proxies = proxy_manager.start(
                auto_test=True, 
                wait=False, 
                find_first=app_config.executor.max_workers,
                threads=app_config.proxy.max_workers
            )
            
            # Converte para modelo Proxy
            for p in raw_proxies:
                proxies_list.append(Proxy(
                    id=str(p.get("tag") or p.get("id")),
                    url=p.get("url", ""),
                    type=p.get("scheme", "http"),
                    country=p.get("country_code")
                ))
            print_success(f"{len(proxies_list)} proxies obtidos.")

    # 4. Prepara Contas
    contas_executar = []
    if email:
        if not password:
            print_error("Senha obrigatória para execução única.")
            raise typer.Exit(1)
        contas_executar.append(Conta(email, password, profile_id or email))
    else:
        print_info(f"Carregando contas de: {source}")
        contas_executar = list(repo.listar())
        if not contas_executar:
            print_error("Nenhuma conta encontrada.")
            raise typer.Exit(1)

    # 5. Configura Repositório de Estado (Redis/Memória)
    # Por padrão usa memória se redis não estiver configurado explicitamente
    # Futuramente: ler app_config.redis_url
    state_repo = InMemorySessionStateRepository()
    mail_service = MailTm(logger=logger)

    # 6. Inicializa Executor
    executor = BatchExecutor(
        state_repository=state_repo,
        max_workers=app_config.executor.max_workers,
        mail_service=mail_service,
        logger=logger
    )
    
    # 7. Executa
    acoes = actions or app_config.executor.actions
    print_info(f"Executando ações: {acoes}")
    
    resultado = executor.executar(contas_executar, acoes, proxies_list)
    
    # 8. Exibe Resultados (UI Layer)
    # 8. Exibe Resultados (UI Layer)
    show_execution_summary({
        "total": resultado.total_contas,
        "sucesso": resultado.sucessos,
        "falha": resultado.falhas,
        "pontos_totais": resultado.total_pontos
    })
    
    if resultado.falhas > 0:
        falhas = [asdict(r) for r in resultado.detalhes if not r.sucesso_geral]
        show_failures(falhas)


@accounts_app.command("list-file")
def list_file_accounts():
    """Lista contas do arquivo."""
    config = get_config()
    repo = FileAccountRepository(config.executor.users_file)
    contas = repo.listar()
    
    data = [{"email": c.email, "pontos": 0, "status": "File"} for c in contas]
    show_accounts_table(data)


@accounts_app.command("list-db")
def list_db_accounts():
    """Lista contas do banco."""
    repo = SupabaseAccountRepository(logger=get_logger())
    contas = repo.listar()
    
    data = [{"email": c.email, "pontos": 0, "status": "DB"} for c in contas]
    show_accounts_table(data)

# Mantendo comandos de proxy legado por enquanto (eles chamam infrastructure.manager)
# A refatoração do proxy está em outro escopo (já feito/planejado separadamente)
@proxy_app.command("test")
def test_proxies(threads: int = 10, country: Optional[str] = None):
    """Testa proxies."""
    proxy_service = ProxyManager(use_console=True)
    proxy_service.test(threads=threads, country=country, verbose=True)

if __name__ == "__main__":
    app()