"""Endpoints para BingFlyout."""

from __future__ import annotations
from fastapi import APIRouter

from raxy.infrastructure.logging import get_logger
from raxy.adapters.http.schemas import FlyoutRequest, FlyoutResponse

router = APIRouter(prefix="/flyout", tags=["Bing Flyout"])
logger = get_logger()


@router.post("", response_model=FlyoutResponse)
def execute_flyout(request: FlyoutRequest) -> FlyoutResponse:
    """Executa ação no Bing Flyout."""
    from raxy.core.services.bingflyout_service import BingFlyoutService
    
    try:
        service = BingFlyoutService(logger=logger)
        
        return FlyoutResponse(
            success=True,
            message="Flyout service disponível. Use com uma sessão autenticada."
        )
    except Exception as e:
        logger.erro(f"Erro no flyout: {e}")
        return FlyoutResponse(success=False, message=str(e))


__all__ = ["router"]
