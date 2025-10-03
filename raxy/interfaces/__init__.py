"""Interfaces públicas utilizadas pelo container de injeção."""

from .services import (
    IAutenticadorRewardsService,
    IExecutorEmLoteService,
    IGerenciadorSolicitacoesService,
    ILoggingService,
    INavegadorRewardsService,
    IPerfilService,
    IRewardsBrowserService,
    IRewardsDataService,
    IBingSuggestion
)
from .repositories import IContaRepository, IHistoricoPontuacaoRepository, IDatabaseRepository

__all__ = [
    "IAutenticadorRewardsService",
    "IContaRepository",
    "IExecutorEmLoteService",
    "IGerenciadorSolicitacoesService",
    "IHistoricoPontuacaoRepository",
    "ILoggingService",
    "INavegadorRewardsService",
    "IPerfilService",
    "IRewardsBrowserService",
    "IRewardsDataService",
    "IBingSuggestion",
    "IDatabaseRepository",
]
