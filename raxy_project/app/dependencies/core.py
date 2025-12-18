"""Integração entre a camada FastAPI e o container de dependências do raxy."""

from __future__ import annotations
from typing import Dict
from fastapi import HTTPException, Request

from raxy.container import ApplicationContainer
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import (
    IBingSuggestion,
    IBingFlyoutService,
    IExecutorEmLoteService,
    ILoggingService,
    IProxyService,
    IRewardsDataService,
    IMailTmService,
)
from raxy.core.session_manager_service import SessionManagerService as SessaoSolicitacoes


def _get_container(request: Request) -> ApplicationContainer:
    from raxy.core.exceptions import ContainerException
    
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise ContainerException("Container de dependências não foi inicializado")
    return container


def _ensure_session_store(request: Request) -> Dict[str, SessaoSolicitacoes]:
    store = getattr(request.app.state, "sessions", None)
    if store is None:
        store = {}
        request.app.state.sessions = store
    return store


def get_proxy_service(request: Request) -> IProxyService:
    return _get_container(request).proxy_service()


def get_logging_service(request: Request) -> ILoggingService:
    return _get_container(request).logger()


def get_rewards_data_service(request: Request) -> IRewardsDataService:
    return _get_container(request).rewards_data_service()


def get_bing_suggestion_service(request: Request) -> IBingSuggestion:
    return _get_container(request).bing_suggestion_service()


def get_executor_service(request: Request) -> IExecutorEmLoteService:
    return _get_container(request).executor_service()


def get_database_repository(request: Request) -> IDatabaseRepository:
    return _get_container(request).database_repository()


def get_account_repository(request: Request) -> IContaRepository:
    return _get_container(request).conta_repository()


def get_mailtm_service(request: Request) -> IMailTmService:
    return _get_container(request).mail_tm_service()


def get_bingflyout_service(request: Request) -> IBingFlyoutService:
    return _get_container(request).bing_flyout_service()


def get_session_store(request: Request) -> Dict[str, SessaoSolicitacoes]:
    return _ensure_session_store(request)


def get_session(request: Request, session_id: str) -> SessaoSolicitacoes:
    store = _ensure_session_store(request)
    if session_id not in store:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return store[session_id]


def delete_session(request: Request, session_id: str) -> None:
    store = _ensure_session_store(request)
    if session_id in store:
        session_object = store.pop(session_id)
        # Limpeza adequada dos recursos da sessão (ex: driver do navegador)
        if hasattr(session_object, 'close') and callable(session_object.close):
            try:
                session_object.close()
            except Exception:
                pass # Ignora erros ao fechar a sessão


def get_task_queue(request: Request):
    """Retorna a fila de tarefas do RQ."""
    queue = getattr(request.app.state, "task_queue", None)
    if queue is None:
        raise HTTPException(status_code=503, detail="Sistema de filas indisponível (Redis desabilitado?)")
    return queue