"""Endpoints para consulta de contas cadastradas."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import get_account_repository, get_database_repository
from schemas import AccountResponse, AccountsResponse, AccountSource
from raxy.domain import Conta
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("", response_model=AccountsResponse)
def list_file_accounts(
    conta_repository: IContaRepository = Depends(get_account_repository),
) -> AccountsResponse:
    """Retorna as contas cadastradas no arquivo ``email:senha``."""

    contas = conta_repository.listar()
    items = [_to_account_response(conta, AccountSource.FILE) for conta in contas]
    return AccountsResponse(accounts=items)


@router.get("/database", response_model=AccountsResponse)
def list_database_accounts(
    database_repository: IDatabaseRepository = Depends(get_database_repository),
) -> AccountsResponse:
    """Lista todas as contas persistidas no banco de dados."""

    registros = database_repository.listar_contas()
    contas = [_from_database_record(registro) for registro in registros]
    items = [item for item in contas if item is not None]
    return AccountsResponse(accounts=items)


def _to_account_response(conta: Conta, source: AccountSource) -> AccountResponse:
    perfil = conta.id_perfil or conta.email
    proxy_value = conta.proxy or None
    senha = getattr(conta, "senha", None)
    return AccountResponse(
        email=conta.email,
        profile_id=perfil,
        password=senha or None,
        proxy=proxy_value,
        source=source,
    )


def _from_database_record(registro: dict | None) -> AccountResponse | None:
    if not isinstance(registro, dict):
        return None

    email = registro.get("email")
    if not email:
        return None

    perfil = (
        registro.get("id_perfil")
        or registro.get("perfil")
        or registro.get("profile_id")
        or email
    )
    proxy = registro.get("proxy") or registro.get("proxy_uri")
    senha = registro.get("senha") or registro.get("password") or ""
    conta = Conta(email=email, senha=senha, id_perfil=str(perfil), proxy=proxy or "")
    return _to_account_response(conta, AccountSource.DATABASE)


__all__ = ["router"]
