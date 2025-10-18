"""Integração entre a camada FastAPI e o container de dependências do raxy."""

from __future__ import annotations
from typing import Dict
from fastapi import HTTPException, Request

from raxy.container import SimpleInjector
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


def _get_injector(request: Request) -> SimpleInjector:
    injector = getattr(request.app.state, "injector", None)
    if injector is None:
        raise RuntimeError("Container de dependências não foi inicializado.")
    return injector


def _ensure_session_store(request: Request) -> Dict[str, SessaoSolicitacoes]:
    store = getattr(request.app.state, "sessions", None)
    if store is None:
        store = {}
        request.app.state.sessions = store
    return store


def get_proxy_service(request: Request) -> IProxyService:
    return _get_injector(request).get(IProxyService)


def get_logging_service(request: Request) -> ILoggingService:
    return _get_injector(request).get(ILoggingService)


def get_rewards_data_service(request: Request) -> IRewardsDataService:
    return _get_injector(request).get(IRewardsDataService)


def get_bing_suggestion_service(request: Request) -> IBingSuggestion:
    return _get_injector(request).get(IBingSuggestion)


def get_executor_service(request: Request) -> IExecutorEmLoteService:
    return _get_injector(request).get(IExecutorEmLoteService)


def get_database_repository(request: Request) -> IDatabaseRepository:
    return _get_injector(request).get(IDatabaseRepository)


def get_account_repository(request: Request) -> IContaRepository:
    return _get_injector(request).get(IContaRepository)


def get_mailtm_service(request: Request) -> IMailTmService:
    return _get_injector(request).get(IMailTmService)


def get_bingflyout_service(request: Request) -> IBingFlyoutService:
    return _get_injector(request).get(IBingFlyoutService)


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