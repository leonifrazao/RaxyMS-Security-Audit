"""Endpoints para autenticação/login."""

from __future__ import annotations
from typing import Dict
from fastapi import APIRouter, Request

from raxy.infrastructure.logging import get_logger
from raxy.adapters.http.schemas import LoginRequest, LoginResponse, SessionResponse

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = get_logger()


def _get_sessions(request: Request) -> Dict:
    """Obtém o store de sessões."""
    if not hasattr(request.app.state, "sessions"):
        request.app.state.sessions = {}
    return request.app.state.sessions


@router.post("/login", response_model=LoginResponse)
def login(request: Request, payload: LoginRequest) -> LoginResponse:
    """Inicia uma sessão de login para uma conta."""
    from raxy.core.services.session_manager_service import SessionManagerService
    from raxy.core.domain.accounts import Conta
    from raxy.infrastructure.config.config import get_config
    import uuid
    
    sessions = _get_sessions(request)
    config = get_config()
    
    try:
        conta = Conta(
            email=payload.email,
            senha=payload.password,
            id_perfil=payload.profile_id or payload.email
        )
        
        session_id = str(uuid.uuid4())
        
        # Cria sessão (não executa login ainda, apenas prepara)
        session = SessionManagerService(
            conta=conta,
            proxy={},
            config=config,
            logger=logger
        )
        
        sessions[session_id] = session
        
        return LoginResponse(
            session_id=session_id,
            email=payload.email,
            status="created",
            message="Sessão criada. Use /auth/start para iniciar o login."
        )
    except Exception as e:
        logger.erro(f"Erro ao criar sessão: {e}")
        return LoginResponse(
            session_id="",
            email=payload.email,
            status="error",
            message=str(e)
        )


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(request: Request) -> list[SessionResponse]:
    """Lista sessões ativas."""
    sessions = _get_sessions(request)
    
    return [
        SessionResponse(
            session_id=sid,
            email=getattr(session.conta, 'email', 'unknown'),
            status="active"
        )
        for sid, session in sessions.items()
    ]


@router.delete("/sessions/{session_id}")
def delete_session(request: Request, session_id: str):
    """Remove uma sessão."""
    sessions = _get_sessions(request)
    
    if session_id in sessions:
        session = sessions.pop(session_id)
        if hasattr(session, 'close'):
            try:
                session.close()
            except Exception:
                pass
        return {"status": "deleted", "session_id": session_id}
    
    return {"status": "not_found", "session_id": session_id}


__all__ = ["router"]