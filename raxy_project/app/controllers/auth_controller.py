"""Endpoints responsáveis por autenticação e manutenção de sessões Rewards."""

from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import (
    delete_session,
    get_logging_service,
    get_session_store,
    get_proxy_service,
    get_mailtm_service,
)
from schemas import AuthRequest, AuthResponse, LoggingOperationResponse, SessionCloseRequest
from raxy.domain import Conta
from raxy.interfaces.services import ILoggingService, IProxyService, IMailTmService
from raxy.core.session_manager_service import SessionManagerService, ProxyRotationRequiredException

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login", response_model=AuthResponse, status_code=201)
def login(
    payload: AuthRequest,
    request: Request,
    logger: ILoggingService = Depends(get_logging_service),
    proxy_service: IProxyService = Depends(get_proxy_service),
    mail_service: IMailTmService = Depends(get_mailtm_service),
) -> AuthResponse:
    """Realiza o login na conta Rewards e retorna um identificador de sessão."""

    profile_id = payload.profile_id or payload.email
    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_id não pôde ser determinado")

    # Objeto Conta não armazena mais o proxy
    conta = Conta(
        email=payload.email,
        senha=payload.password,
        id_perfil=profile_id,
    )

    try:
        # O proxy é passado como um detalhe de execução para o SessionManagerService
        sessao = SessionManagerService(
            conta=conta,
            proxy=payload.proxy,
            proxy_service=proxy_service,
            mail_service=mail_service,
        )
        sessao.start()
    except ProxyRotationRequiredException as exc:
        logger.erro("Falha de proxy ao autenticar usuário via API", erro=str(exc))
        raise HTTPException(status_code=503, detail=f"Proxy error during authentication: {exc.status_code}") from exc
    except Exception as exc:
        logger.erro("Falha ao autenticar usuário via API", erro=str(exc), exc_info=True)
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
    """Remove a sessão mantida em memória e encerra seus recursos."""

    if not payload.session_id:
        raise HTTPException(status_code=400, detail="session_id é obrigatório")

    delete_session(request, payload.session_id)
    logger.info("Sessão removida via API", sessao=payload.session_id)
    return LoggingOperationResponse(status="session_closed", level="info")