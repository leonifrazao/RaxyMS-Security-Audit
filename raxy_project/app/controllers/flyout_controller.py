"""Endpoints para executar o fluxo de Bing Flyout."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import get_bingflyout_service, get_session
from schemas import FlyoutExecuteRequest, FlyoutExecuteResponse
from raxy.interfaces.services import IBingFlyoutService

router = APIRouter(prefix="/flyout", tags=["Flyout"])


@router.post("/execute", response_model=FlyoutExecuteResponse)
def execute_flyout(
    payload: FlyoutExecuteRequest,
    request: Request,
    flyout_service: IBingFlyoutService = Depends(get_bingflyout_service),
) -> FlyoutExecuteResponse:
    """Executa o fluxo de onboarding do Bing Flyout para uma sessão autenticada."""
    
    sessao = get_session(request, payload.session_id)
    try:
        flyout_service.executar(sessao)
    except Exception as exc:
        raise HTTPException(
            status_code=500, 
            detail=f"Falha ao executar flyout: {str(exc)}"
        ) from exc
    
    return FlyoutExecuteResponse(
        status="success",
        detail="Flyout executado com sucesso",
        session_id=payload.session_id
    )


__all__ = ["router"]
