"""Endpoints responsáveis por autenticação e manutenção de sessões Rewards."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import (
    delete_session,
    get_auth_service,
    get_logging_service,
    get_perfil_service,
    get_session_store,
)
from schemas import AuthRequest, AuthResponse, LoggingOperationResponse, SessionCloseRequest
from raxy.domain import Conta
from raxy.interfaces.services import IAutenticadorRewardsService, ILoggingService, IPerfilService
from raxy.core.session_service import SessaoSolicitacoes

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=AuthResponse, status_code=201)
def login(
    payload: AuthRequest,
    request: Request,
    autenticador: IAutenticadorRewardsService = Depends(get_auth_service),
    perfil_service: IPerfilService = Depends(get_perfil_service),
    logger: ILoggingService = Depends(get_logging_service),
) -> AuthResponse:
    """Realiza o login na conta Rewards e retorna um identificador de sessão."""

    profile_id = payload.profile_id or payload.email
    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_id não pôde ser determinado")

    perfil_service.garantir_perfil(profile_id, payload.email, payload.password)

    conta = Conta(email=payload.email, senha=payload.password, id_perfil=profile_id, proxy=(payload.proxy or {}).get("uri", ""))

    try:
        sessao: SessaoSolicitacoes = autenticador.executar(conta, proxy=payload.proxy)
    except Exception as exc:  # pragma: no cover - dependente de integração real
        logger.erro("Falha ao autenticar usuário via API", erro=str(exc))
        raise HTTPException(status_code=500, detail="Não foi possível autenticar a conta") from exc

    session_id = str(uuid.uuid4())
    store = get_session_store(request)
    store[session_id] = sessao

    logger.sucesso("Sessão criada via API", sessao=session_id, conta=payload.email)
    return AuthResponse(session_id=session_id, profile_id=profile_id, email=payload.email)


@router.post("/logout", response_model=LoggingOperationResponse)
def logout(
    payload: SessionCloseRequest,
    request: Request,
    logger: ILoggingService = Depends(get_logging_service),
) -> LoggingOperationResponse:
    """Remove a sessão mantida em memória."""

    if not payload.session_id:
        raise HTTPException(status_code=400, detail="session_id é obrigatório")

    delete_session(request, payload.session_id)
    logger.info("Sessão removida via API", sessao=payload.session_id)
    return LoggingOperationResponse(status="session_closed", level="info")
