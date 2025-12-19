"""Endpoints para consumir a API de Rewards sem navegador."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import get_rewards_data_service, get_session
from schemas import RewardsPointsRequest, RewardsRedeemRequest, RewardsResponse
from core import BaseController
from raxy.interfaces.services import IRewardsDataService


class RewardsController(BaseController):
    """Controller para gerenciamento de rewards."""
    
    def __init__(self):
        super().__init__()
        self.router = APIRouter(prefix="/rewards", tags=["Rewards"])
        self._register_routes()
    
    def _register_routes(self):
        """Registra as rotas do controller."""
        self.router.add_api_route(
            "/points",
            self.get_points,
            methods=["POST"],
            response_model=RewardsResponse
        )
        self.router.add_api_route(
            "/redeem",
            self.redeem_rewards,
            methods=["POST"],
            response_model=RewardsResponse
        )


    def get_points(
        self,
        payload: RewardsPointsRequest,
        request: Request,
        rewards_service: IRewardsDataService = Depends(get_rewards_data_service),
    ) -> RewardsResponse:
        """Obtém os pontos de rewards de uma sessão."""
        self.validate_session_id(payload.session_id)
        self.log_request("get_points", {"session_id": payload.session_id})
        
        try:
            sessao = get_session(request, payload.session_id)
            pontos = rewards_service.obter_pontos(
                sessao, 
                bypass_request_token=payload.bypass_request_token
            )
            
            response = RewardsResponse(status="ok", data={"points": pontos})
            self.log_response("get_points", {"points": pontos})
            return response
        except HTTPException:
            raise
        except Exception as exc:
            self.handle_service_error(exc, "get_points")
    
    def redeem_rewards(
        self,
        payload: RewardsRedeemRequest,
        request: Request,
        rewards_service: IRewardsDataService = Depends(get_rewards_data_service),
    ) -> RewardsResponse:
        """Resgata recompensas de uma sessão."""
        self.validate_session_id(payload.session_id)
        self.log_request("redeem_rewards", {"session_id": payload.session_id})
        
        try:
            sessao = get_session(request, payload.session_id)
            resultado = rewards_service.pegar_recompensas(
                sessao,
                bypass_request_token=payload.bypass_request_token
            )
            
            response = RewardsResponse(status="ok", data={"result": resultado})
            self.log_response("redeem_rewards", {"result": resultado})
            return response
        except HTTPException:
            raise
        except Exception as exc:
            self.handle_service_error(exc, "redeem_rewards")


# Cria instância do controller e exporta o router
controller = RewardsController()
router = controller.router

__all__ = ["router", "RewardsController"]