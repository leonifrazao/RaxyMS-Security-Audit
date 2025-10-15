"""Interfaces relacionadas a serviços."""

from .IExecutorEmLoteService import IExecutorEmLoteService
from .ILoggingService import ILoggingService
from .IPerfilService import IPerfilService
from .IProxyService import IProxyService
from .IRewardsDataService import IRewardsDataService
from .IBingSuggestion import IBingSuggestion
from .IBingFlyoutService import IBingFlyoutService

__all__ = [
    "IExecutorEmLoteService",
    "ILoggingService",
    "INavegadorRewardsService",
    "IPerfilService",
    "IProxyService",
    "IRewardsDataService",
    "IBingSuggestion",
    "IBingFlyoutService",
]
