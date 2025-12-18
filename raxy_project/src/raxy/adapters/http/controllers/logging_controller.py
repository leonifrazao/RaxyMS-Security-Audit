"""Endpoints para logging."""

from __future__ import annotations
from fastapi import APIRouter

from raxy.infrastructure.logging import get_logger
from raxy.adapters.http.schemas import LogRequest, LogResponse

router = APIRouter(prefix="/logs", tags=["Logging"])
logger = get_logger()


@router.post("", response_model=LogResponse)
def log_message(request: LogRequest) -> LogResponse:
    """Registra uma mensagem de log."""
    try:
        level = request.level.lower()
        
        if level == "info":
            logger.info(request.message, **request.extra or {})
        elif level == "warning" or level == "aviso":
            logger.aviso(request.message, **request.extra or {})
        elif level == "error" or level == "erro":
            logger.erro(request.message, **request.extra or {})
        elif level == "debug":
            logger.debug(request.message, **request.extra or {})
        elif level == "success" or level == "sucesso":
            logger.sucesso(request.message, **request.extra or {})
        else:
            logger.info(request.message, **request.extra or {})
        
        return LogResponse(success=True, message="Log registrado")
    except Exception as e:
        return LogResponse(success=False, message=str(e))


@router.get("/levels")
def get_log_levels():
    """Retorna os níveis de log disponíveis."""
    return {
        "levels": ["debug", "info", "success", "warning", "error"]
    }


__all__ = ["router"]