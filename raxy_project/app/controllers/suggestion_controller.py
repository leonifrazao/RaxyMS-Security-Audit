"""Endpoints para sugestões do Bing Rewards."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import get_bing_suggestion_service, get_session
from app.schemas import SuggestionRequest, SuggestionResponse
from app.core import BaseController
from raxy.interfaces.services import IBingSuggestion


class SuggestionController(BaseController):
    """Controller para gerenciamento de sugestões."""
    
    def __init__(self):
        super().__init__()
        self.router = APIRouter(prefix="/suggestions", tags=["Suggestions"])
        self._register_routes()
    
    def _register_routes(self):
        """Registra as rotas do controller."""
        self.router.add_api_route(
            "/all",
            self.get_all_suggestions,
            methods=["POST"],
            response_model=SuggestionResponse
        )
        self.router.add_api_route(
            "/random",
            self.get_random_suggestion,
            methods=["POST"]
        )


    def get_all_suggestions(
        self,
        payload: SuggestionRequest,
        request: Request,
        suggestion_service: IBingSuggestion = Depends(get_bing_suggestion_service),
    ) -> SuggestionResponse:
        """Obtém todas as sugestões para uma palavra-chave."""
        self.validate_session_id(payload.session_id)
        self.log_request("get_all_suggestions", {
            "session_id": payload.session_id,
            "keyword": payload.keyword
        })
        
        try:
            sessao = get_session(request, payload.session_id)
            sugestoes = suggestion_service.get_all(sessao, payload.keyword)
            total = len(sugestoes) if isinstance(sugestoes, list) else 0
            
            response = SuggestionResponse(
                status="ok",
                total=total,
                suggestions=sugestoes or []
            )
            self.log_response("get_all_suggestions", {"total": total})
            return response
        except HTTPException:
            raise
        except Exception as exc:
            self.handle_service_error(exc, "get_all_suggestions")
    
    def get_random_suggestion(
        self,
        payload: SuggestionRequest,
        request: Request,
        suggestion_service: IBingSuggestion = Depends(get_bing_suggestion_service),
    ):
        """Obtém uma sugestão aleatória para uma palavra-chave."""
        self.validate_session_id(payload.session_id)
        self.log_request("get_random_suggestion", {
            "session_id": payload.session_id,
            "keyword": payload.keyword
        })
        
        try:
            sessao = get_session(request, payload.session_id)
            sugestao = suggestion_service.get_random(sessao, payload.keyword)
            
            response = {"status": "ok", "suggestion": sugestao}
            self.log_response("get_random_suggestion", {"suggestion": sugestao})
            return response
        except HTTPException:
            raise
        except Exception as exc:
            self.handle_service_error(exc, "get_random_suggestion")


# Cria instância do controller e exporta o router
controller = SuggestionController()
router = controller.router

__all__ = ["router", "SuggestionController"]