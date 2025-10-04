"""Interfaces relacionadas a repositórios."""

from .IContaRepository import IContaRepository
from .IHistoricoPontuacaoRepository import IHistoricoPontuacaoRepository
from .IDatabaseRepository import IDatabaseRepository

__all__ = [
    "IContaRepository",
    "IHistoricoPontuacaoRepository",
    "IDatabaseRepository",
]