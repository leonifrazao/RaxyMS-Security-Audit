"""
Sistema de injeção de dependências do Raxy.

Gerencia todas as dependências da aplicação usando dependency-injector
(Inversion of Control) para gerenciamento profissional de dependências.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from dependency_injector import containers, providers

# Configuração centralizada
from raxy.core.config import AppConfig, ExecutorConfig, get_config

# Interfaces
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import (
    IExecutorEmLoteService,
    ILoggingService,
    IRewardsDataService,
    IProxyService,
    IBingSuggestion,
    IBingFlyoutService,
    IMailTmService,
    IEventBus,
)

# Implementações
from raxy.repositories.file_account_repository import ArquivoContaRepository
from raxy.services.executor_service import ExecutorEmLote
from raxy.core.logging import get_logger
from raxy.api.rewards_data_api import RewardsDataAPI
from raxy.api.bing_suggestion_api import BingSuggestionAPI
from raxy.api.supabase_api import SupabaseRepository
from raxy.services.bingflyout_service import BingFlyoutService
from raxy.proxy import Proxy
from raxy.api.mail_tm_api import MailTm
from raxy.domain import InfraServices
from raxy.core.events import RedisEventBus


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
    
    # Logging
    logger = providers.Singleton(get_logger)
    
    # Event Bus (Redis Pub/Sub)
    event_bus = providers.Singleton(
        lambda config, logger: RedisEventBus(
            host=config.events.host,
            port=config.events.port,
            db=config.events.db,
            password=config.events.password,
            prefix=config.events.prefix,
            logger=logger,
        ) if config.events.enabled else None,
        config=config,
        logger=logger
    )
    
    # Proxies
    proxy_service = providers.Singleton(
        Proxy,
        country=config.provided.proxy.country,
        sources=config.provided.proxy.sources,
        use_console=config.provided.proxy.use_console,
        # Usa o cache configurado
        cache_path=providers.Callable(
            lambda cfg: Path(__file__).parent / "proxy" / cfg.proxy.cache_filename,
            cfg=config
        ),
        # Event Bus para publicar eventos de proxy
        event_bus=event_bus
    )
    
    # APIs
    rewards_data_service = providers.Singleton(
        RewardsDataAPI,
        event_bus=event_bus
    )
    bing_suggestion_service = providers.Singleton(BingSuggestionAPI)
    bing_flyout_service = providers.Singleton(BingFlyoutService)
    mail_tm_service = providers.Singleton(MailTm)
    
    # Repositórios
    database_repository = providers.Singleton(
        lambda config: SupabaseRepository(
            url=config.api.supabase_url,
            key=config.api.supabase_key
        ) if config.api.has_supabase else None,
        config=config
    )
    
    conta_repository = providers.Singleton(
        ArquivoContaRepository,
        caminho_arquivo=executor_config.provided.users_file
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
        logger=logger,
        mail_tm_service=mail_tm_service
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
        logger=logger,
        event_bus=event_bus
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
        _container = ApplicationContainer()
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
