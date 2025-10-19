"""Módulo de dependências da API."""

from .base import get_injector, get_session_store
from .services import (
    get_proxy_service,
    get_logging_service,
    get_rewards_data_service,
    get_bing_suggestion_service,
    get_executor_service,
    get_mailtm_service,
    get_bingflyout_service,
)
from .repositories import (
    get_database_repository,
    get_account_repository,
)
from .session import (
    get_session,
    delete_session,
)

__all__ = [
    # Base
    "get_injector",
    "get_session_store",
    # Services
    "get_proxy_service",
    "get_logging_service",
    "get_rewards_data_service",
    "get_bing_suggestion_service",
    "get_executor_service",
    "get_mailtm_service",
    "get_bingflyout_service",
    # Repositories
    "get_database_repository",
    "get_account_repository",
    # Session
    "get_session",
    "delete_session",
]
