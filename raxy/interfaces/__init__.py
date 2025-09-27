"""Interfaces públicas utilizadas pelo container de injeção."""

from .services import (
    IAPIRecompensasService,
    IAutenticadorRewardsService,
    IExecutorEmLoteService,
    IGerenciadorSolicitacoesService,
    ILoggingService,
    INavegadorRewardsService,
    IPerfilService,
    IRewardsBrowserService,
    IRewardsDataService,
)
from .repositories import IContaRepository, IHistoricoPontuacaoRepository

__all__ = [
    "IAPIRecompensasService",
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
]
