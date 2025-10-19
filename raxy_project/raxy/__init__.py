"""API pública do pacote Raxy."""

from raxy.api.rewards_data_api import RewardsDataAPI
from raxy.container import create_injector, get_injector
from raxy.domain import Conta
from raxy.repositories.file_account_repository import (
    ArquivoContaRepository,
    HistoricoPontuacaoMemoriaRepository,
)
from raxy.services.executor_service import ExecutorEmLote
from raxy.core.config import ExecutorConfig, AppConfig, get_config
from raxy.core.logging import get_logger, LoggerConfig

# Compatibilidade com código antigo
log = get_logger()

__all__ = [
    "ArquivoContaRepository",
    "Conta",
    "ExecutorConfig",
    "ExecutorEmLote",
    "HistoricoPontuacaoMemoriaRepository",
    "LoggerConfig",
    "RewardsDataAPI",
    "AppConfig",
    "create_injector",
    "get_injector",
    "get_config",
    "get_logger",
    "log",
]
