"""Endpoints para consulta de contas cadastradas."""

from __future__ import annotations
from typing import List
from fastapi import APIRouter

from raxy.infrastructure.logging import get_logger
from raxy.infrastructure.config.config import get_config
from raxy.adapters.http.schemas import (
    AccountResponse,
    AccountsResponse,
    AccountSource,
)
from raxy.core.domain.accounts import Conta

router = APIRouter(prefix="/accounts", tags=["Accounts"])
logger = get_logger()


@router.get("", response_model=AccountsResponse)
def list_file_accounts() -> AccountsResponse:
    """Retorna as contas cadastradas no arquivo."""
    from raxy.adapters.repositories.file_account_repository import ArquivoContaRepository
    
    config = get_config()
    repo = ArquivoContaRepository(config.executor.users_file)
    
    try:
        contas = repo.listar()
        items = [
            AccountResponse(
                email=conta.email,
                profile_id=conta.id_perfil or conta.email,
                password=getattr(conta, "senha", None),
                proxy=None,
                source=AccountSource.FILE,
            )
            for conta in contas
        ]
        return AccountsResponse(accounts=items)
    except Exception as e:
        logger.erro(f"Erro ao listar contas: {e}")
        raise


@router.get("/database", response_model=AccountsResponse)
def list_database_accounts() -> AccountsResponse:
    """Lista todas as contas persistidas no banco de dados."""
    try:
        from raxy.adapters.api.supabase_api import SupabaseRepository
        
        repo = SupabaseRepository(logger=logger)
        
        # Verifica se o cliente de DB está disponível
        if repo._db_client is None:
            logger.aviso("Cliente Supabase não configurado (verifique SUPABASE_URL e SUPABASE_KEY)")
            return AccountsResponse(accounts=[])
        
        registros = repo.listar_contas()
        
        items = []
        for registro in registros:
            if not isinstance(registro, dict) or not registro.get("email"):
                continue
            
            items.append(AccountResponse(
                email=registro["email"],
                profile_id=registro.get("id_perfil") or registro.get("perfil") or registro["email"],
                password=registro.get("senha") or registro.get("password"),
                proxy=registro.get("proxy"),
                source=AccountSource.DATABASE,
            ))
        
        return AccountsResponse(accounts=items)
    except Exception as e:
        logger.erro(f"Erro ao listar contas do banco: {e}")
        return AccountsResponse(accounts=[])


__all__ = ["router"]