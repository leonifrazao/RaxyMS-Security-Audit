"""
Adapter para Supabase que implementa IDatabaseClient.

Encapsula a biblioteca supabase-py seguindo a interface padronizada.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Sequence

from supabase import create_client, Client

from raxy.interfaces.database import IDatabaseClient


class SupabaseDatabaseClient(IDatabaseClient):
    """
    Adapter para Supabase.
    
    Implementa IDatabaseClient delegando para supabase-py,
    permitindo trocar para PostgreSQL direto ou outro DB no futuro.
    
    Design Pattern: Adapter Pattern
    Princípio: Dependency Inversion Principle (DIP)
    """
    
    def __init__(self, url: str, key: str):
        """
        Inicializa cliente Supabase.
        
        Args:
            url: URL do projeto Supabase
            key: API Key do Supabase
        """
        self._client: Client = create_client(url, key)
    
    def upsert(
        self,
        table: str,
        data: Dict[str, Any],
        on_conflict: str
    ) -> Optional[Dict[str, Any]]:
        """Insere ou atualiza registro."""
        try:
            response = self._client.table(table).upsert(
                data,
                on_conflict=on_conflict
            ).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception:
            return None
    
    def select(
        self,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> Sequence[Dict[str, Any]]:
        """Seleciona registros."""
        try:
            query = self._client.table(table).select(columns)
            
            # Aplica filtros
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            # Aplica limite
            if limit:
                query = query.limit(limit)
            
            response = query.execute()
            return response.data if response.data else []
        except Exception:
            return []
    
    def select_one(
        self,
        table: str,
        filters: Dict[str, Any],
        columns: str = "*"
    ) -> Optional[Dict[str, Any]]:
        """Seleciona um único registro."""
        results = self.select(table, columns, filters, limit=1)
        return results[0] if results else None
    
    def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Atualiza registros."""
        try:
            query = self._client.table(table).update(data)
            
            # Aplica filtros
            for key, value in filters.items():
                query = query.eq(key, value)
            
            response = query.execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception:
            return None
    
    def delete(
        self,
        table: str,
        filters: Dict[str, Any]
    ) -> bool:
        """Remove registros."""
        try:
            query = self._client.table(table).delete()
            
            # Aplica filtros
            for key, value in filters.items():
                query = query.eq(key, value)
            
            query.execute()
            return True
        except Exception:
            return False
    
    def health_check(self) -> bool:
        """Verifica saúde da conexão."""
        try:
            # Tenta fazer uma query simples
            self._client.table("contas").select("email").limit(1).execute()
            return True
        except Exception:
            return False
    
    def get_native_client(self) -> Client:
        """
        Retorna cliente nativo do Supabase.
        
        NOTA: Use apenas quando absolutamente necessário.
        Evite vazamento de abstração.
        
        Returns:
            Client: Cliente nativo do Supabase
        """
        return self._client
