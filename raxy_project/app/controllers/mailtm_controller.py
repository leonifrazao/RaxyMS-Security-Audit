"""Endpoints para gerenciar contas de email temporário via Mail.tm."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_mailtm_service
from schemas import (
    MailTmCreateAccountRequest,
    MailTmCreateAccountResponse,
    MailTmGetMessagesResponse,
    MailTmGetMessageResponse,
    MailTmGetDomainsResponse,
)
from raxy.interfaces.services import IMailTmService

router = APIRouter(prefix="/mailtm", tags=["MailTm"])


@router.get("/domains", response_model=MailTmGetDomainsResponse)
def get_domains(
    mail_service: IMailTmService = Depends(get_mailtm_service),
) -> MailTmGetDomainsResponse:
    """Retorna a lista de domínios disponíveis no Mail.tm."""
    
    try:
        domains = mail_service.get_domains()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao obter domínios: {str(exc)}"
        ) from exc
    
    return MailTmGetDomainsResponse(domains=domains)


@router.post("/accounts", response_model=MailTmCreateAccountResponse)
def create_account(
    payload: MailTmCreateAccountRequest,
    mail_service: IMailTmService = Depends(get_mailtm_service),
) -> MailTmCreateAccountResponse:
    """Cria uma nova conta de email temporário."""
    
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
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao criar conta: {str(exc)}"
        ) from exc
    
    return MailTmCreateAccountResponse(
        address=result.get("address", ""),
        password=result.get("password", ""),
        token=result.get("token", ""),
    )


@router.get("/messages", response_model=MailTmGetMessagesResponse)
def get_messages(
    page: int = 1,
    mail_service: IMailTmService = Depends(get_mailtm_service),
) -> MailTmGetMessagesResponse:
    """Recupera mensagens da caixa de entrada."""
    
    try:
        messages = mail_service.get_messages(page=page)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao obter mensagens: {str(exc)}"
        ) from exc
    
    return MailTmGetMessagesResponse(messages=messages)


@router.get("/messages/{message_id}", response_model=MailTmGetMessageResponse)
def get_message(
    message_id: str,
    mail_service: IMailTmService = Depends(get_mailtm_service),
) -> MailTmGetMessageResponse:
    """Recupera uma mensagem específica."""
    
    try:
        message = mail_service.get_message(message_id)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Mensagem não encontrada: {str(exc)}"
        ) from exc
    
    return MailTmGetMessageResponse(message=message)


__all__ = ["router"]
