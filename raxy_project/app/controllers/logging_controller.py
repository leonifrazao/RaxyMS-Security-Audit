"""Endpoints utilitários do serviço de logging."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import get_logging_service, get_session
from schemas import LoggingMessageRequest, LoggingOperationResponse
from raxy.interfaces.services import ILoggingService

router = APIRouter(prefix="/logging", tags=["Logging"])


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


@router.post("/message", response_model=LoggingOperationResponse)
def log_message(
    payload: LoggingMessageRequest,
    request: Request,
    logger: ILoggingService = Depends(get_logging_service),
) -> LoggingOperationResponse:
    """Permite registrar mensagens customizadas via API."""

    level_key = _LEVEL_MAP.get(payload.level.lower()) if payload.level else None
    if not level_key:
        raise HTTPException(status_code=400, detail="Nível de log inválido")

    scoped_logger = logger
    if payload.session_id:
        try:
            sessao = get_session(request, payload.session_id)
            scoped_logger = logger.com_contexto(perfil=sessao.perfil, email=sessao.conta.email)
        except HTTPException:
            # Se a sessão não existir, mantém logger padrão
            scoped_logger = logger

    metodo = getattr(scoped_logger, level_key, None)
    if not callable(metodo):  # pragma: no cover - segurança adicional
        raise HTTPException(status_code=500, detail="Logger não suporta o nível solicitado")

    metodo(payload.message, **(payload.extra or {}))
    return LoggingOperationResponse(status="logged", level=level_key)
