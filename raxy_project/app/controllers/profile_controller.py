"""Endpoints relacionados ao gerenciamento de perfis."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_perfil_service
from ..schemas import ProfileEnsureRequest, ProfileEnsureResponse
from raxy.interfaces.services import IPerfilService

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.post("/ensure", response_model=ProfileEnsureResponse, status_code=201)
def ensure_profile(
    payload: ProfileEnsureRequest,
    perfil_service: IPerfilService = Depends(get_perfil_service),
) -> ProfileEnsureResponse:
    """Garante que o perfil informado exista antes das rotinas do Rewards."""

    if not payload.profile_id:
        raise HTTPException(status_code=400, detail="profile_id é obrigatório")

    perfil_service.garantir_perfil(payload.profile_id, payload.email, payload.password)
    return ProfileEnsureResponse(profile_id=payload.profile_id)
