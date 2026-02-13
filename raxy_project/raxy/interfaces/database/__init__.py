"""Interfaces para abstração de sistemas de armazenamento e banco de dados."""

from .IFileSystem import IFileSystem
from .IContaRepository import IContaRepository
from .IDatabaseRepository import IDatabaseRepository
from .IDatabaseClient import IDatabaseClient
from .IHistoricoPontuacaoRepository import IHistoricoPontuacaoRepository

__all__ = [
    "IFileSystem",
    "IContaRepository",
    "IDatabaseRepository",
    "IDatabaseClient",
    "IHistoricoPontuacaoRepository",
]
