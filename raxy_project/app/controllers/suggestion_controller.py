"""Endpoints para sugestões do Bing Rewards."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import get_bing_suggestion_service, get_session
from schemas import SuggestionRequest, SuggestionResponse
from raxy.interfaces.services import IBingSuggestion

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])


@router.post("/all", response_model=SuggestionResponse)
def get_all_suggestions(
    payload: SuggestionRequest,
    request: Request,
    suggestion_service: IBingSuggestion = Depends(get_bing_suggestion_service),
) -> SuggestionResponse:
    sessao = get_session(request, payload.session_id)
    try:
        sugestoes = suggestion_service.get_all(sessao.base_request, payload.keyword)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    total = len(sugestoes) if isinstance(sugestoes, list) else 0
    return SuggestionResponse(status="ok", total=total, suggestions=sugestoes or [])


@router.post("/random")
def get_random_suggestion(
    payload: SuggestionRequest,
    request: Request,
    suggestion_service: IBingSuggestion = Depends(get_bing_suggestion_service),
):
    sessao = get_session(request, payload.session_id)
    try:
        sugestao = suggestion_service.get_random(sessao.base_request, payload.keyword)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", "suggestion": sugestao}
