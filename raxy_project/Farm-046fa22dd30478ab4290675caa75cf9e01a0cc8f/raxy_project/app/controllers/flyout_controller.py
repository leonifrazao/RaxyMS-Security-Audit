"""Endpoints para executar o fluxo de Bing Flyout."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import get_bingflyout_service, get_session
from schemas import FlyoutExecuteRequest, FlyoutExecuteResponse
from core import BaseController
from raxy.interfaces.services import IBingFlyoutService


class FlyoutController(BaseController):
    """Controller para gerenciamento do Bing Flyout."""
    
    def __init__(self):
        super().__init__()
        self.router = APIRouter(prefix="/flyout", tags=["Flyout"])
        self._register_routes()
    
    def _register_routes(self):
        """Registra as rotas do controller."""
        self.router.add_api_route(
            "/execute",
            self.execute_flyout,
            methods=["POST"],
            response_model=FlyoutExecuteResponse
        )
    
    def execute_flyout(
        self,
        payload: FlyoutExecuteRequest,
        request: Request,
        flyout_service: IBingFlyoutService = Depends(get_bingflyout_service),
    ) -> FlyoutExecuteResponse:
        """Executa o fluxo de onboarding do Bing Flyout para uma sessão autenticada."""
        self.validate_session_id(payload.session_id)
        self.log_request("execute_flyout", {"session_id": payload.session_id})
        
        try:
            sessao = get_session(request, payload.session_id)
            flyout_service.executar(sessao)
            
            response = FlyoutExecuteResponse(
                status="success",
                detail="Flyout executado com sucesso",
                session_id=payload.session_id
            )
            self.log_response("execute_flyout", {"status": "success"})
            return response
        except HTTPException:
            raise
        except Exception as exc:
            self.handle_service_error(exc, "execute_flyout")


# Cria instância do controller e exporta o router
controller = FlyoutController()
router = controller.router

__all__ = ["router", "FlyoutController"]
