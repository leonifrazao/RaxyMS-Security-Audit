"""Endpoints para sugestões Bing."""

from __future__ import annotations
from fastapi import APIRouter

from raxy.infrastructure.logging import get_logger
from raxy.adapters.http.schemas import SuggestionRequest, SuggestionResponse

router = APIRouter(prefix="/suggestions", tags=["Bing Suggestions"])
logger = get_logger()


@router.post("", response_model=SuggestionResponse)
def get_suggestions(request: SuggestionRequest) -> SuggestionResponse:
    """Obtém sugestões de busca do Bing."""
    from raxy.adapters.api.bing_suggestion_api import BingSuggestionAPI
    
    try:
        api = BingSuggestionAPI(logger=logger)
        suggestions = api.get_all(request.query)
        
        return SuggestionResponse(
            query=request.query,
            suggestions=suggestions,
            success=True
        )
    except Exception as e:
        logger.erro(f"Erro ao obter sugestões: {e}")
        return SuggestionResponse(
            query=request.query,
            suggestions=[],
            success=False,
            error=str(e)
        )


__all__ = ["router"]