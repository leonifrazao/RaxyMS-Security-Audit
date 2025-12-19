"""API pública do pacote Raxy."""

from raxy.api.rewards_data_api import RewardsDataAPI
from raxy.container import ApplicationContainer, get_container, reset_container, override_config
from raxy.domain import Conta
from raxy.repositories.file_account_repository import (
    ArquivoContaRepository,
    HistoricoPontuacaoMemoriaRepository,
)
from raxy.services.executor_service import ExecutorEmLote
from raxy.core.config import (
    ExecutorConfig,
    AppConfig,
    get_config,
    set_config,
    update_config,
    reload_config,
    reset_config,
)
from raxy.core.logging import get_logger, LoggerConfig

# Compatibilidade com código antigo
log = get_logger()

__all__ = [
    # Domínio e repositórios
    "ArquivoContaRepository",
    "Conta",
    "HistoricoPontuacaoMemoriaRepository",
    
    # Serviços
    "ExecutorEmLote",
    "RewardsDataAPI",
    
    # Configuração
    "ExecutorConfig",
    "AppConfig",
    "get_config",
    "set_config",
    "update_config",
    "reload_config",
    "reset_config",
    
    # Dependency Injection
    "ApplicationContainer",
    "get_container",
    "reset_container",
    "override_config",
    
    # Logging
    "LoggerConfig",
    "get_logger",
    "log",
]
