"""
Sistema de injeção de dependências do Raxy.

Gerencia todas as dependências da aplicação usando dependency-injector
(Inversion of Control) para gerenciamento profissional de dependências.
"""

from __future__ import annotations

from pathlib import Path
from pathlib import Path

from dependency_injector import containers, providers

# Configuração centralizada
from raxy.core.config import AppConfig, ExecutorConfig, get_config

# Interfaces
# (Interfaces removidas pois não são usadas diretamente no container, apenas as implementações)

# Implementações
from raxy.infrastructure.database import SQLiteRepository, SupabaseRepository
from raxy.services.executor_service import ExecutorEmLote
from raxy.core.logging import get_logger
from raxy.infrastructure.api.rewards_data_api import RewardsDataAPI
from raxy.infrastructure.api.bing_suggestion_api import BingSuggestionAPI
from raxy.services.bingflyout_service import BingFlyoutService
from raxy.services.dashboard_service import LiveDashboardService
from raxy.infrastructure.proxy import Proxy
from raxy.infrastructure.proxy.process import ProcessManager
from raxy.infrastructure.proxy.network import NetworkManager
from raxy.infrastructure.api.mail_tm_api import MailTm
from raxy.models import InfraServices



class ApplicationContainer(containers.DeclarativeContainer):
    """
    Container de injeção de dependências da aplicação.
    
    Usa o framework dependency-injector para gerenciar todas as
    dependências da aplicação de forma declarativa e profissional.
    """
    
    # Configuração da aplicação
    config = providers.Singleton(get_config)
    
    executor_config = providers.Singleton(
        lambda config: config.executor,
        config=config
    )
    
    # Logging base
    base_logger = providers.Singleton(get_logger)
    
    # Logger genérico
    logger = providers.Singleton(get_logger)
    
    # Loggers específicos por serviço (usando logger padrão)
    rewards_logger = providers.Singleton(get_logger)
    
    flyout_logger = providers.Singleton(get_logger)
    
    bing_logger = providers.Singleton(get_logger)
    
    executor_logger = providers.Singleton(get_logger)
    
    session_logger = providers.Singleton(get_logger)
    
    # Gerenciadores de Proxy Internos
    proxy_process_manager = providers.Singleton(ProcessManager)
    
    proxy_network_manager = providers.Singleton(
        NetworkManager,
        requests_session=None, # Define session provider if needed later
        process_manager=proxy_process_manager
    )

    # Proxies
    proxy_service = providers.Singleton(
        Proxy,
        process_manager=proxy_process_manager,
        network_manager=proxy_network_manager,
        country=config.provided.proxy.country,
        sources=config.provided.proxy.sources,
        use_console=config.provided.proxy.use_console,
        # Usa o cache configurado
        cache_path=providers.Callable(
            lambda cfg: Path(__file__).parent / "infrastructure" / "proxy" / cfg.proxy.cache_filename,
            cfg=config
        )
    )
    
    # APIs
    rewards_data_service = providers.Singleton(
        RewardsDataAPI,
        logger=rewards_logger
    )
    bing_suggestion_service = providers.Singleton(
        BingSuggestionAPI,
        logger=bing_logger
    )
    bing_flyout_service = providers.Singleton(
        BingFlyoutService,
        logger=flyout_logger
    )
    mail_tm_service = providers.Singleton(MailTm)
    
    # Repositórios
    conta_repository = providers.Singleton(
        SQLiteRepository,
        db_path="raxy.db"
    )

    database_repository = providers.Singleton(
        lambda config, sqlite_repo: SupabaseRepository(
            url=config.api.supabase_url,
            key=config.api.supabase_key
        ) if config.api.has_supabase else sqlite_repo,
        config=config,
        sqlite_repo=conta_repository
    )
    
    # Serviços de Negócio
    dashboard_service = providers.Singleton(
        LiveDashboardService,
        logger=base_logger,
        enabled=executor_config.provided.enable_dashboard
    )
    
    # Serviços de infraestrutura
    infra_services = providers.Singleton(
        InfraServices,
        conta_repository=conta_repository,
        rewards_data=rewards_data_service,
        db_repository=database_repository,
        bing_search=bing_suggestion_service,
        bing_flyout_service=bing_flyout_service,
        proxy_manager=proxy_service,
        logger=base_logger,
        mail_tm_service=mail_tm_service,
        dashboard=dashboard_service
    )
    
    # Configuração de proxy
    proxy_config = providers.Singleton(
        lambda config: config.proxy,
        config=config
    )
    
    # Executor em lote
    executor_service = providers.Singleton(
        ExecutorEmLote,
        services=infra_services,
        config=executor_config,
        proxy_config=proxy_config,
        logger=executor_logger
    )


# Container global (singleton)
_container: ApplicationContainer | None = None


def get_container() -> ApplicationContainer:
    """
    Obtém o container global da aplicação.
    
    Returns:
        ApplicationContainer: Instância singleton do container
    """
    global _container
    if _container is None:
        # Import local para evitar ciclo se get_logger depender de algo que usa container (improvável mas seguro)
        from raxy.core.logging import get_logger
        logger = get_logger()
        logger.debug("Inicializando ApplicationContainer (Singleton)")
        
        _container = ApplicationContainer()
        
        logger.debug("ApplicationContainer inicializado com sucesso")
        
    return _container


def override_config(config: AppConfig) -> None:
    """
    Sobrescreve a configuração do container global.
    
    Args:
        config: Nova configuração da aplicação
    """
    container = get_container()
    container.config.override(providers.Singleton(lambda: config))


def reset_container() -> None:
    """Reseta o container global e suas dependências."""
    global _container
    if _container is not None:
        _container.reset_singletons()
        _container = None


__all__ = [
    "ApplicationContainer",
    "get_container",
    "override_config",
    "reset_container",
]
