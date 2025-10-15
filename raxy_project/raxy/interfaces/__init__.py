"""Interfaces públicas utilizadas pelo container de injeção."""

from .services import (
    IExecutorEmLoteService,
    ILoggingService,
    IPerfilService,
    IRewardsDataService,
    IBingSuggestion
)
from .repositories import IContaRepository, IHistoricoPontuacaoRepository, IDatabaseRepository

__all__ = [
    "IAutenticadorRewardsService",
    "IContaRepository",
    "IExecutorEmLoteService",
    "IHistoricoPontuacaoRepository",
    "ILoggingService",
    "IPerfilService",
    "IRewardsDataService",
    "IBingSuggestion",
    "IDatabaseRepository",
]
