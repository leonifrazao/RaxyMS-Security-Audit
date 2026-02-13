
"""
Repositório de banco de dados usando Supabase.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, List
from datetime import datetime, timezone

from supabase import create_client, Client

from raxy.interfaces.database import (
    IDatabaseRepository,
    IContaRepository,
    IDatabaseClient,
)
from raxy.interfaces.services import ILoggingService
from raxy.models import Conta
from raxy.core.exceptions import ValidationException, wrap_exception
from raxy.core.config import get_config


class SupabaseDatabaseClient(IDatabaseClient):
    """
    Adapter para Supabase.
    
    Implementa IDatabaseClient delegando para supabase-py.
    """
    
    def __init__(self, url: str, key: str):
        self._client: Client = create_client(url, key)
    
    def upsert(self, table: str, data: Dict[str, Any], on_conflict: str) -> Optional[Dict[str, Any]]:
        try:
            response = self._client.table(table).upsert(data, on_conflict=on_conflict).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception:
            return None
    
    def select(self, table: str, columns: str = "*", filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> Sequence[Dict[str, Any]]:
        try:
            query = self._client.table(table).select(columns)
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            if limit:
                query = query.limit(limit)
            response = query.execute()
            return response.data if response.data else []
        except Exception:
            return []
    
    def select_one(self, table: str, filters: Dict[str, Any], columns: str = "*") -> Optional[Dict[str, Any]]:
        results = self.select(table, columns, filters, limit=1)
        return results[0] if results else None
    
    def update(self, table: str, data: Dict[str, Any], filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            query = self._client.table(table).update(data)
            for key, value in filters.items():
                query = query.eq(key, value)
            response = query.execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception:
            return None
    
    def delete(self, table: str, filters: Dict[str, Any]) -> bool:
        try:
            query = self._client.table(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            query.execute()
            return True
        except Exception:
            return False

    def health_check(self) -> bool:
        try:
            self._client.table("contas").select("email").limit(1).execute()
            return True
        except Exception:
            return False


class SupabaseConfig:
    """Configuração para Supabase."""
    TABLE_CONTAS = "contas"
    
    @classmethod
    def from_config(cls) -> tuple[str, str]:
        config = get_config().api
        url = config.supabase_url
        key = config.supabase_key
        if not url or not key:
            raise ValidationException("Credenciais do Supabase não encontradas na configuração")
        return url, key


class SupabaseRepository(IDatabaseRepository, IContaRepository):
    """
    Repositório de banco de dados usando Supabase.
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        logger: Optional[ILoggingService] = None,
        db_client: Optional[IDatabaseClient] = None
    ):
        from raxy.core.logging import get_logger
        self._logger = logger or get_logger()
        self.config = SupabaseConfig()
        
        if db_client is None:
            if not url or not key:
                try:
                    url, key = self.config.from_config()
                except ValidationException:
                    self._logger.aviso("Credenciais Supabase não encontradas. Funcionalidade limitada.")
            
            if url and key:
                # Use local client class
                db_client = SupabaseDatabaseClient(url, key)
                self._logger.info("Cliente Supabase inicializado com sucesso")
        
        self._db_client = db_client

    # IContaRepository Implementation

    def listar(self) -> List[Conta]:
        rows = self.listar_contas()
        return [Conta.from_dict(row) for row in rows]

    def salvar(self, conta: Conta) -> Conta:
        data = conta.to_dict()
        result = self._db_client.upsert(
            table=self.config.TABLE_CONTAS,
            data=data,
            on_conflict="email"
        )
        if result:
            return Conta.from_dict(result[0] if isinstance(result, list) else result)
        return conta

    def salvar_varias(self, contas: Sequence[Conta]) -> Sequence[Conta]:
        data = [c.to_dict() for c in contas]
        self._db_client.upsert(
            table=self.config.TABLE_CONTAS,
            data=data,
            on_conflict="email"
        )
        return contas

    def remover(self, conta: Conta) -> None:
        self._db_client.delete(
            table=self.config.TABLE_CONTAS,
            filters={"email": conta.email}
        )

    # IDatabaseRepository Implementation

    def adicionar_registro_farm(self, email: str, pontos: int) -> Optional[Conta]:
        self._logger.info("Adicionando/atualizando registro de farm (Supabase)", email=email, pontos=pontos)
        timestamp = datetime.now(timezone.utc).isoformat()
        data = {
            "email": email,
            "pontos": pontos,
            "ultima_farm": timestamp,
        }
        try:
            result = self._db_client.upsert(
                table=self.config.TABLE_CONTAS,
                data=data,
                on_conflict="email"
            )
            if result:
                return Conta.from_dict(result[0] if isinstance(result, list) else result)
            return None
        except Exception as e:
            self._logger.erro("Erro ao adicionar registro farm no Supabase", exception=e)
            return None
    
    def consultar_conta(self, email: str) -> Optional[Conta]:
        try:
            result = self._db_client.select_one(
                table=self.config.TABLE_CONTAS,
                filters={"email": email},
                columns="*"
            )
            return Conta.from_dict(result) if result else None
        except Exception as e:
            self._logger.erro("Erro ao consultar conta no Supabase", exception=e)
            return None

    def listar_contas(self) -> List[Conta]:
        try:
            results = self._db_client.select(
                table=self.config.TABLE_CONTAS,
                columns="*"
            )
            return [Conta.from_dict(r) for r in results]
        except Exception as e:
            self._logger.erro("Erro ao listar contas no Supabase", exception=e)
            return []
