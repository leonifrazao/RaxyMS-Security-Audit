"""Interfaces relacionadas a serviços."""

from .IExecutorEmLoteService import IExecutorEmLoteService
from .ILoggingService import ILoggingService
from .IProxyService import IProxyService
from .IRewardsDataService import IRewardsDataService
from .IBingSuggestion import IBingSuggestion
from .IBingFlyoutService import IBingFlyoutService
from .IMailTmService import IMailTmService
from .IEventBus import IEventBus
from .ISessionManager import ISessionManager

__all__ = [
    "IExecutorEmLoteService",
    "ILoggingService",
    "INavegadorRewardsService",
    "IProxyService",
    "IRewardsDataService",
    "IBingSuggestion",
    "IBingFlyoutService",
    "IMailTmService",
    "IEventBus",
    "ISessionManager",
]
