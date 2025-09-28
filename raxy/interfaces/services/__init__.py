"""Interfaces relacionadas a serviços."""

from .IAutenticadorRewardsService import IAutenticadorRewardsService
from .IAPIRecompensasService import IAPIRecompensasService
from .IExecutorEmLoteService import IExecutorEmLoteService
from .IGerenciadorSolicitacoesService import IGerenciadorSolicitacoesService
from .ILoggingService import ILoggingService
from .INavegadorRewardsService import INavegadorRewardsService
from .IPerfilService import IPerfilService
from .IProxyService import IProxyService
from .IRewardsBrowserService import IRewardsBrowserService
from .IRewardsDataService import IRewardsDataService

__all__ = [
    "IAPIRecompensasService",
    "IAutenticadorRewardsService",
    "IExecutorEmLoteService",
    "IGerenciadorSolicitacoesService",
    "ILoggingService",
    "INavegadorRewardsService",
    "IPerfilService",
    "IProxyService",
    "IRewardsBrowserService",
    "IRewardsDataService",
]
