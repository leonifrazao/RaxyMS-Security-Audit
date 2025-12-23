"""Interfaces públicas utilizadas pelo container de injeção."""

from .services import (
    IExecutorEmLoteService,
    ILoggingService,
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
    "IRewardsDataService",
    "IBingSuggestion",
    "IDatabaseRepository",
]
