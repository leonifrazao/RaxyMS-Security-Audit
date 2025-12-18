"""Endpoints para gerenciar contas de email temporário via Mail.tm."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_mailtm_service
from app.schemas import (
    MailTmCreateAccountRequest,
    MailTmCreateAccountResponse,
    MailTmGetMessagesResponse,
    MailTmGetMessageResponse,
    MailTmGetDomainsResponse,
)
from app.core import BaseController
from raxy.interfaces.services import IMailTmService


class MailTmController(BaseController):
    """Controller para gerenciamento de email temporário."""
    
    def __init__(self):
        super().__init__()
        self.router = APIRouter(prefix="/mailtm", tags=["MailTm"])
        self._register_routes()
    
    def _register_routes(self):
        """Registra as rotas do controller."""
        self.router.add_api_route(
            "/domains",
            self.get_domains,
            methods=["GET"],
            response_model=MailTmGetDomainsResponse
        )
        self.router.add_api_route(
            "/accounts",
            self.create_account,
            methods=["POST"],
            response_model=MailTmCreateAccountResponse
        )
        self.router.add_api_route(
            "/messages",
            self.get_messages,
            methods=["GET"],
            response_model=MailTmGetMessagesResponse
        )
        self.router.add_api_route(
            "/messages/{message_id}",
            self.get_message,
            methods=["GET"],
            response_model=MailTmGetMessageResponse
        )


    def get_domains(
        self,
        mail_service: IMailTmService = Depends(get_mailtm_service),
    ) -> MailTmGetDomainsResponse:
        """Retorna a lista de domínios disponíveis no Mail.tm."""
        self.log_request("get_domains")
        
        try:
            domains = mail_service.get_domains()
            response = MailTmGetDomainsResponse(domains=domains)
            self.log_response("get_domains", {"count": len(domains)})
            return response
        except Exception as exc:
            self.handle_service_error(exc, "get_domains")


    def create_account(
        self,
        payload: MailTmCreateAccountRequest,
        mail_service: IMailTmService = Depends(get_mailtm_service),
    ) -> MailTmCreateAccountResponse:
        """Cria uma nova conta de email temporário."""
        self.log_request("create_account", {"random": payload.random})
        
        try:
            if payload.random:
                result = mail_service.create_random_account(
                    password=payload.password,
                    max_attempts=20,
                    delay=1
                )
            else:
                if not payload.address:
                    raise HTTPException(
                        status_code=400,
                        detail="address é obrigatório quando random=false"
                    )
                result = mail_service.create_account(
                    address=payload.address,
                    password=payload.password or "defaultPassword123"
                )
            
            response = MailTmCreateAccountResponse(
                address=result.get("address", ""),
                password=result.get("password", ""),
                token=result.get("token", ""),
            )
            self.log_response("create_account", {"address": result.get("address")})
            return response
        except HTTPException:
            raise
        except Exception as exc:
            self.handle_service_error(exc, "create_account")


    def get_messages(
        self,
        page: int = 1,
        mail_service: IMailTmService = Depends(get_mailtm_service),
    ) -> MailTmGetMessagesResponse:
        """Recupera mensagens da caixa de entrada."""
        self.log_request("get_messages", {"page": page})
        
        try:
            messages = mail_service.get_messages(page=page)
            response = MailTmGetMessagesResponse(messages=messages)
            self.log_response("get_messages", {"count": len(messages)})
            return response
        except Exception as exc:
            self.handle_service_error(exc, "get_messages")


    def get_message(
        self,
        message_id: str,
        mail_service: IMailTmService = Depends(get_mailtm_service),
    ) -> MailTmGetMessageResponse:
        """Recupera uma mensagem específica."""
        self.log_request("get_message", {"message_id": message_id})
        
        try:
            message = mail_service.get_message(message_id)
            response = MailTmGetMessageResponse(message=message)
            self.log_response("get_message", {"message_id": message_id})
            return response
        except Exception as exc:
            if "not found" in str(exc).lower():
                raise HTTPException(
                    status_code=404,
                    detail=f"Mensagem não encontrada: {str(exc)}"
                ) from exc
            self.handle_service_error(exc, "get_message")


# Cria instância do controller e exporta o router
controller = MailTmController()
router = controller.router

__all__ = ["router", "MailTmController"]
