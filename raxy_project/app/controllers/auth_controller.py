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
from core import BaseController
from raxy.domain import Conta
from raxy.interfaces.services import ILoggingService, IProxyService, IMailTmService
from raxy.core.session_manager_service import SessionManagerService, ProxyRotationRequiredException


class AuthController(BaseController):
    """Controller para autenticação e gerenciamento de sessões."""
    
    def __init__(self):
        super().__init__()
        self.router = APIRouter(prefix="/auth", tags=["Auth"])
        self._register_routes()
    
    def _register_routes(self):
        """Registra as rotas do controller."""
        self.router.add_api_route(
            "/login",
            self.login,
            methods=["POST"],
            response_model=AuthResponse,
            status_code=201
        )
        self.router.add_api_route(
            "/logout",
            self.logout,
            methods=["POST"],
            response_model=LoggingOperationResponse
        )

    def login(
        self,
        payload: AuthRequest,
        request: Request,
        logger: ILoggingService = Depends(get_logging_service),
        proxy_service: IProxyService = Depends(get_proxy_service),
        mail_service: IMailTmService = Depends(get_mailtm_service),
    ) -> AuthResponse:
        """Realiza o login na conta Rewards e retorna um identificador de sessão."""
        self.log_request("login", {"email": payload.email})
        
        profile_id = payload.profile_id or payload.email
        if not profile_id:
            raise HTTPException(status_code=400, detail="profile_id não pôde ser determinado")
        
        conta = Conta(
            email=payload.email,
            senha=payload.password,
            id_perfil=profile_id,
        )
        
        try:
            sessao = SessionManagerService(
                conta=conta,
                proxy=payload.proxy,
                proxy_service=proxy_service,
                mail_service=mail_service,
            )
            sessao.start()
        except ProxyRotationRequiredException as exc:
            logger.erro("Falha de proxy ao autenticar usuário via API", erro=str(exc))
            raise HTTPException(
                status_code=503,
                detail=f"Proxy error during authentication: {exc.status_code}"
            ) from exc
        except Exception as exc:
            logger.erro("Falha ao autenticar usuário via API", erro=str(exc), exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Não foi possível autenticar a conta"
            ) from exc
        
        session_id = str(uuid.uuid4())
        store = get_session_store(request)
        store[session_id] = sessao
        
        logger.sucesso("Sessão criada via API", sessao=session_id, conta=payload.email)
        
        response = AuthResponse(
            session_id=session_id,
            profile_id=profile_id,
            email=payload.email
        )
        self.log_response("login", {"session_id": session_id})
        return response


    def logout(
        self,
        payload: SessionCloseRequest,
        request: Request,
        logger: ILoggingService = Depends(get_logging_service),
    ) -> LoggingOperationResponse:
        """Remove a sessão mantida em memória e encerra seus recursos."""
        self.validate_session_id(payload.session_id)
        self.log_request("logout", {"session_id": payload.session_id})
        
        try:
            delete_session(request, payload.session_id)
            logger.info("Sessão removida via API", sessao=payload.session_id)
            
            response = LoggingOperationResponse(status="session_closed", level="info")
            self.log_response("logout", {"session_id": payload.session_id})
            return response
        except Exception as e:
            self.handle_service_error(e, "logout")


# Cria instância do controller e exporta o router
controller = AuthController()
router = controller.router

__all__ = ["router", "AuthController"]