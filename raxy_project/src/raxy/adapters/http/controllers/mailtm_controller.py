"""Endpoints para MailTM."""

from __future__ import annotations
from fastapi import APIRouter

from raxy.infrastructure.logging import get_logger
from raxy.adapters.http.schemas import (
    MailTmAccountRequest,
    MailTmAccountResponse,
    MailTmMessagesResponse,
)

router = APIRouter(prefix="/mailtm", tags=["MailTM"])
logger = get_logger()


@router.get("/domains")
def list_domains():
    """Lista domínios disponíveis no MailTM."""
    from raxy.adapters.api.mail_tm_api import MailTm
    
    try:
        api = MailTm(logger=logger)
        domains = api.get_domains()
        
        # Serializa Domain objects para dict
        domain_list = []
        for d in domains:
            if hasattr(d, 'domain'):
                domain_list.append({"id": d.id, "domain": d.domain})
            elif isinstance(d, dict):
                domain_list.append(d)
            else:
                domain_list.append(str(d))
        
        return {"domains": domain_list, "count": len(domain_list), "success": True}
    except Exception as e:
        logger.erro(f"Erro ao listar domínios: {e}")
        return {"domains": [], "success": False, "error": str(e)}


@router.post("/account", response_model=MailTmAccountResponse)
def create_account(request: MailTmAccountRequest) -> MailTmAccountResponse:
    """Cria uma conta temporária no MailTM."""
    from raxy.adapters.api.mail_tm_api import MailTm
    
    try:
        api = MailTm(logger=logger)
        
        # Se não passar address/password, cria conta aleatória
        if not request.address or not request.password:
            result = api.create_random_account(password=request.password)
        else:
            result = api.create_account(
                address=request.address,
                password=request.password
            )
        
        return MailTmAccountResponse(
            success=True,
            email=result.account.address if result else "",
            token=result.token if result else "",
            message="Conta criada com sucesso"
        )
    except Exception as e:
        logger.erro(f"Erro ao criar conta: {e}")
        return MailTmAccountResponse(
            success=False,
            email="",
            token="",
            message=str(e)
        )


@router.get("/messages/{token}", response_model=MailTmMessagesResponse)
def get_messages(token: str) -> MailTmMessagesResponse:
    """Lista mensagens de uma conta MailTM."""
    from raxy.adapters.api.mail_tm_api import MailTm
    
    try:
        api = MailTm(logger=logger)
        messages = api.listar_mensagens(token)
        
        return MailTmMessagesResponse(
            success=True,
            messages=[
                {"id": m.id, "subject": m.subject, "from": m.from_address.address}
                for m in messages
            ] if messages else []
        )
    except Exception as e:
        logger.erro(f"Erro ao listar mensagens: {e}")
        return MailTmMessagesResponse(success=False, messages=[], error=str(e))


__all__ = ["router"]
