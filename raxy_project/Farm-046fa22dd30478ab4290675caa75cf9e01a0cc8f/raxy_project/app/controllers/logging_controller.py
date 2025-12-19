"""Endpoints utilitários do serviço de logging."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import get_logging_service, get_session
from schemas import LoggingMessageRequest, LoggingOperationResponse
from core import BaseController
from raxy.interfaces.services import ILoggingService


class LoggingController(BaseController):
    """Controller para gerenciamento de logs."""
    
    _LEVEL_MAP = {
        "debug": "debug",
        "info": "info",
        "sucesso": "sucesso",
        "success": "sucesso",
        "aviso": "aviso",
        "warning": "aviso",
        "erro": "erro",
        "error": "erro",
        "critico": "critico",
        "critical": "critico",
    }
    
    def __init__(self):
        super().__init__()
        self.router = APIRouter(prefix="/logging", tags=["Logging"])
        self._register_routes()
    
    def _register_routes(self):
        """Registra as rotas do controller."""
        self.router.add_api_route(
            "/message",
            self.log_message,
            methods=["POST"],
            response_model=LoggingOperationResponse
        )


    def log_message(
        self,
        payload: LoggingMessageRequest,
        request: Request,
        logger: ILoggingService = Depends(get_logging_service),
    ) -> LoggingOperationResponse:
        """Permite registrar mensagens customizadas via API."""
        self.log_request("log_message", {
            "level": payload.level,
            "session_id": payload.session_id
        })
        
        level_key = self._LEVEL_MAP.get(payload.level.lower()) if payload.level else None
        if not level_key:
            raise HTTPException(status_code=400, detail="Nível de log inválido")
        
        scoped_logger = logger
        if payload.session_id:
            try:
                sessao = get_session(request, payload.session_id)
                scoped_logger = logger.com_contexto(
                    perfil=sessao.conta.id_perfil,
                    email=sessao.conta.email
                )
            except HTTPException:
                # Se a sessão não existir, mantém logger padrão
                scoped_logger = logger
        
        metodo = getattr(scoped_logger, level_key, None)
        if not callable(metodo):
            raise HTTPException(
                status_code=500,
                detail="Logger não suporta o nível solicitado"
            )
        
        try:
            metodo(payload.message, **(payload.extra or {}))
            response = LoggingOperationResponse(status="logged", level=level_key)
            self.log_response("log_message", {"level": level_key})
            return response
        except Exception as e:
            self.handle_service_error(e, "log_message")


# Cria instância do controller e exporta o router
controller = LoggingController()
router = controller.router

__all__ = ["router", "LoggingController"]