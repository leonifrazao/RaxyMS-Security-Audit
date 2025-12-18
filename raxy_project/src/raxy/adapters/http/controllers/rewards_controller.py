"""Endpoints para rewards."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException

from raxy.infrastructure.logging import get_logger
from raxy.adapters.http.schemas import RewardsDataRequest, RewardsDataResponse

router = APIRouter(prefix="/rewards", tags=["Rewards"])
logger = get_logger()


def _get_session(session_id: str):
    """Busca uma sessão ativa pelo ID."""
    # TODO: Implementar store de sessões global
    raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")


@router.post("/data", response_model=RewardsDataResponse)
def get_rewards_data(request: RewardsDataRequest) -> RewardsDataResponse:
    """Obtém dados do Microsoft Rewards para uma sessão."""
    from raxy.adapters.api.rewards_data_api import RewardsDataAPI
    
    try:
        # Se tiver session_id, usa os cookies da sessão
        # Por enquanto, apenas demonstra a estrutura
        api = RewardsDataAPI(logger=logger)
        
        return RewardsDataResponse(
            success=True,
            message="Use /auth/login primeiro para criar uma sessão",
            data={}
        )
    except Exception as e:
        logger.erro(f"Erro ao obter dados rewards: {e}")
        return RewardsDataResponse(
            success=False,
            message=str(e),
            data={}
        )


__all__ = ["router"]