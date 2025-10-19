"""Dependências de sessão."""

from __future__ import annotations

from fastapi import HTTPException, Request

from .base import get_session_store
from raxy.core.session_manager_service import SessionManagerService


def get_session(request: Request, session_id: str) -> SessionManagerService:
    """
    Obtém uma sessão específica pelo ID.
    
    Args:
        request: Request do FastAPI
        session_id: ID da sessão
        
    Returns:
        SessionManagerService: Sessão encontrada
        
    Raises:
        HTTPException: Se a sessão não for encontrada
    """
    store = get_session_store(request)
    if session_id not in store:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return store[session_id]


def delete_session(request: Request, session_id: str) -> None:
    """
    Remove uma sessão do armazenamento.
    
    Args:
        request: Request do FastAPI
        session_id: ID da sessão a remover
    """
    store = get_session_store(request)
    if session_id in store:
        session_object = store.pop(session_id)
        # Limpeza adequada dos recursos da sessão (ex: driver do navegador)
        if hasattr(session_object, 'close') and callable(session_object.close):
            try:
                session_object.close()
            except Exception:
                pass  # Ignora erros ao fechar a sessão
