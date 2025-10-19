"""Dependências base da aplicação."""

from __future__ import annotations

from typing import Dict
from fastapi import Request

from raxy.container import SimpleInjector
from raxy.core.session_manager_service import SessionManagerService


def get_injector(request: Request) -> SimpleInjector:
    """
    Obtém o container de injeção de dependências.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        SimpleInjector: Container de dependências
        
    Raises:
        RuntimeError: Se o container não foi inicializado
    """
    injector = getattr(request.app.state, "injector", None)
    if injector is None:
        raise RuntimeError("Container de dependências não foi inicializado")
    return injector


def get_session_store(request: Request) -> Dict[str, SessionManagerService]:
    """
    Obtém o armazenamento de sessões.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        Dict[str, SessionManagerService]: Dicionário de sessões
    """
    store = getattr(request.app.state, "sessions", None)
    if store is None:
        store = {}
        request.app.state.sessions = store
    return store
