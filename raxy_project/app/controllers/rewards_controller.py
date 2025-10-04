"""Endpoints para consumir a API de Rewards sem navegador."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..dependencies import get_rewards_data_service, get_session
from ..schemas import RewardsPointsRequest, RewardsRedeemRequest, RewardsResponse
from raxy.interfaces.services import IRewardsDataService

router = APIRouter(prefix="/rewards", tags=["Rewards"])


@router.post("/points", response_model=RewardsResponse)
def get_points(
    payload: RewardsPointsRequest,
    request: Request,
    rewards_service: IRewardsDataService = Depends(get_rewards_data_service),
) -> RewardsResponse:
    sessao = get_session(request, payload.session_id)
    try:
        pontos = rewards_service.obter_pontos(sessao.base_request, bypass_request_token=payload.bypass_request_token)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RewardsResponse(status="ok", data={"points": pontos})


@router.post("/redeem", response_model=RewardsResponse)
def redeem_rewards(
    payload: RewardsRedeemRequest,
    request: Request,
    rewards_service: IRewardsDataService = Depends(get_rewards_data_service),
) -> RewardsResponse:
    sessao = get_session(request, payload.session_id)
    try:
        resultado = rewards_service.pegar_recompensas(sessao.base_request, bypass_request_token=payload.bypass_request_token)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RewardsResponse(status="ok", data={"result": resultado})
