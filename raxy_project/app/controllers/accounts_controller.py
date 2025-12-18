"""Endpoints para consulta de contas cadastradas."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_account_repository, get_database_repository
from app.schemas import (
    AccountPayload,
    AccountResponse,
    AccountUpdatePayload,
    CreateAccountResponse,
    AccountsResponse,
    AccountSource,
)
from app.core import BaseController
from raxy.domain import Conta
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository


class AccountsController(BaseController):
    """Controller para gerenciamento de contas."""
    
    def __init__(self):
        super().__init__()
        self.router = APIRouter(prefix="/accounts", tags=["Accounts"])
        self._register_routes()
    
    def _register_routes(self):
        """Registra as rotas do controller."""
        self.router.add_api_route(
            "",
            self.list_file_accounts,
            methods=["GET"],
            response_model=AccountsResponse
        )
        self.router.add_api_route(
            "/database",
            self.list_database_accounts,
            methods=["GET"],
            response_model=AccountsResponse
        )
    
    def list_file_accounts(
        self,
        conta_repository: IContaRepository = Depends(get_account_repository),
    ) -> AccountsResponse:
        """Retorna as contas cadastradas no arquivo ``email:senha``."""
        self.log_request("list_file_accounts")
        
        try:
            contas = conta_repository.listar()
            items = [self._to_account_response_from_conta(conta, AccountSource.FILE) for conta in contas]
            response = AccountsResponse(accounts=items)
            
            self.log_response("list_file_accounts", {"count": len(items)})
            return response
        except Exception as e:
            self.handle_service_error(e, "list_file_accounts")
    
    def list_database_accounts(
        self,
        database_repository: IDatabaseRepository = Depends(get_database_repository),
    ) -> AccountsResponse:
        """Lista todas as contas persistidas no banco de dados."""
        self.log_request("list_database_accounts")
        
        try:
            # Verifica se o repositório está disponível
            if database_repository is None:
                self.logger.aviso("Database repository não configurado (Supabase não está disponível)")
                return AccountsResponse(accounts=[])
            
            registros = database_repository.listar_contas()
            items = [self._from_database_record_to_response(registro) for registro in registros]
            valid_items = [item for item in items if item is not None]
            response = AccountsResponse(accounts=valid_items)
            
            self.log_response("list_database_accounts", {"count": len(valid_items)})
            return response
        except Exception as e:
            self.handle_service_error(e, "list_database_accounts")
    
    @staticmethod
    def _to_account_response_from_conta(conta: Conta, source: AccountSource) -> AccountResponse:
        """Cria uma AccountResponse a partir de um objeto Conta."""
        perfil = conta.id_perfil or conta.email
        senha = getattr(conta, "senha", None)
        return AccountResponse(
            email=conta.email,
            profile_id=perfil,
            password=senha or None,
            proxy=None,
            source=source,
        )
    
    @staticmethod
    def _from_database_record_to_response(registro: dict | None) -> AccountResponse | None:
        """Cria uma AccountResponse de um registro do banco."""
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
        
        return AccountResponse(
            email=email,
            profile_id=str(perfil),
            password=senha or None,
            proxy=proxy or None,
            source=AccountSource.DATABASE,
        )


# Cria instância do controller e exporta o router
controller = AccountsController()
router = controller.router

__all__ = ["router", "AccountsController"]