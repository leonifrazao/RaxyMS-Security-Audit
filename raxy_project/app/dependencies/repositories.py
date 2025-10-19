"""Dependências de repositórios."""

from __future__ import annotations

from fastapi import Request

from .base import get_injector
from raxy.interfaces.repositories import (
    IContaRepository,
    IDatabaseRepository,
)


def get_database_repository(request: Request) -> IDatabaseRepository:
    """
    Obtém o repositório de banco de dados.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        IDatabaseRepository: Repositório de banco de dados
    """
    return get_injector(request).get(IDatabaseRepository)


def get_account_repository(request: Request) -> IContaRepository:
    """
    Obtém o repositório de contas.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        IContaRepository: Repositório de contas
    """
    return get_injector(request).get(IContaRepository)
