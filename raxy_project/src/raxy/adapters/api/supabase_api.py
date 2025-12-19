"""
Repositório Supabase refatorado com interfaces.
"""

from __future__ import annotations
import os
from typing import Any, Dict, Optional, Sequence
from supabase import create_client

from raxy.core.interfaces import AccountRepository
from raxy.core.models import Conta
from raxy.core.exceptions import DatabaseException, ValidationException
from raxy.adapters.api.base_api import BaseAPIClient

class SupabaseAccountRepository(BaseAPIClient, AccountRepository):
    """
    Implementação oficial do repositório de contas usando Supabase.
    """
    
    def __init__(self, url: str = None, key: str = None, logger: Any = None):
        super().__init__(base_url=url or "", logger=logger)
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        self.table_name = "contas"
        
        if self.url and self.key:
            self.client = create_client(self.url, self.key)
        else:
            self.client = None
            if logger:
                logger.aviso("Supabase config ausente. Repositório em modo offline.")

    def listar(self) -> Sequence[Conta]:
        """Lista contas do Supabase."""
        if not self.client:
            return []
            
        try:
            response = self.client.table(self.table_name).select("*").execute()
            data = response.data
            
            contas = []
            for row in data:
                # Adaptação de schema
                email = row.get("email")
                # Supabase geralmente não salva senha em plain text, 
                # então isso pode ser limitado dependendo do uso.
                # Assumindo uso de 'metadata' ou campos customizados.
                if email:
                    contas.append(Conta(
                        email=email,
                        senha=row.get("senha", ""), # Cuidado com senhas
                        id_perfil=row.get("profile_id")
                    ))
            return contas
        except Exception as e:
            self.logger.erro(f"Erro ao listar do Supabase: {e}")
            return []

    def atualizar_pontos(self, email: str, pontos: int) -> bool:
        """Atualiza a pontuação."""
        if not self.client:
            return False
            
        try:
            data = {"pontos": pontos, "last_updated": "now()"}
            self.client.table(self.table_name).update(data).eq("email", email).execute()
            return True
        except Exception as e:
            self.logger.erro(f"Erro ao atualizar pontos: {e}")
            return False
