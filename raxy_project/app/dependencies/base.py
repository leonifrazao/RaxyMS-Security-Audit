"""Dependências base da aplicação."""

from __future__ import annotations

from typing import Dict
from fastapi import Request

from raxy.container import ApplicationContainer
from raxy.core.session_manager_service import SessionManagerService


def get_container(request: Request) -> ApplicationContainer:
    """
    Obtém o container de injeção de dependências.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        ApplicationContainer: Container de dependências
        
    Raises:
        RuntimeError: Se o container não foi inicializado
    """
    from raxy.core.exceptions import ContainerException
    
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise ContainerException("Container de dependências não foi inicializado")
    return container


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
