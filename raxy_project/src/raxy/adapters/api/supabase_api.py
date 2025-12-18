"""
Repositório refatorado para banco de dados Supabase.

Implementa interface de repositório com Supabase seguindo
padrões de arquitetura limpa e tratamento robusto de erros.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Mapping, Sequence

from dotenv import load_dotenv
from supabase import create_client, Client

from raxy.core.exceptions import (
    DatabaseException,
    ValidationException,
    wrap_exception,
)

# Carrega variáveis de ambiente
load_dotenv()

class SupabaseConfig:
    """Configuração para Supabase."""
    
    # Tabelas
    TABLE_CONTAS = "contas"
    
    # Campos obrigatórios
    REQUIRED_ENV_VARS = ["SUPABASE_URL", "SUPABASE_KEY"]
    
    # Timeouts
    DEFAULT_TIMEOUT = 30
    
    @classmethod
    def from_env(cls) -> tuple[str, str]:
        """
        Carrega configurações do ambiente.
        
        Returns:
            tuple[str, str]: URL e chave do Supabase
            
        Raises:
            ValidationException: Se configuração faltando
        """
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            missing = []
            if not url:
                missing.append("SUPABASE_URL")
            if not key:
                missing.append("SUPABASE_KEY")
            
            raise ValidationException(
                "Credenciais do Supabase não encontradas",
                details={"missing_vars": missing}
            )
        
        return url, key


from .base_api import BaseAPIClient

class SupabaseRepository(BaseAPIClient):
    """
    Repositório de banco de dados usando Supabase.
    
    Desacoplado através da interface IDatabaseClient,
    permitindo trocar entre Supabase real e mock para testes.
    
    Design Pattern: Dependency Injection
    Princípio: Dependency Inversion Principle (DIP)
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        logger: Optional[Any] = None,
        db_client: Optional[Any] = None
    ):
        """
        Inicializa o repositório.
        
        Args:
            url: URL do Supabase (opcional, usa env se não fornecido)
            key: Chave do Supabase (opcional, usa env se não fornecido)
            logger: Serviço de logging
            db_client: Cliente de banco (se None, cria SupabaseDatabaseClient)
        """
        self.config = SupabaseConfig()
        
        # Obtém credenciais se não fornecidas
        if not url or not key:
            try:
                env_url, env_key = self.config.from_env()
                url = url or env_url
                key = key or env_key
            except ValidationException:
                # Se falhar e não tiver db_client, vai dar erro depois
                pass

        super().__init__(base_url=url or "https://supabase.io", logger=logger)
        
        # Dependency Injection: recebe db_client ou cria padrão
        if db_client is None and url and key:
            # Cria cliente Supabase padrão
            from raxy.database import SupabaseDatabaseClient
            db_client = SupabaseDatabaseClient(url, key)
            self.logger.info("Cliente Supabase inicializado com sucesso")
        
        self._db_client = db_client

    def adicionar_registro_farm(self, email: str, pontos: int) -> Optional[Dict[str, Any]]:
        """
        Adiciona ou atualiza registro de farm.
        
        Args:
            email: Email da conta
            pontos: Pontos obtidos
            
        Returns:
            Optional[Dict[str, Any]]: Registro atualizado ou None se erro
        """
        # Valida entrada
        self._validate_farm_input(email, pontos)
        
        self.logger.info(
            "Adicionando/atualizando registro de farm",
            email=email,
            pontos=pontos
        )
        
        def _call():
            # Prepara dados
            timestamp = datetime.now(timezone.utc).isoformat()
            data = {
                "email": email,
                "pontos": pontos,
                "ultima_farm": timestamp,
            }
            
            # Operação upsert usando IDatabaseClient
            return self._db_client.upsert(
                table=self.config.TABLE_CONTAS,
                data=data,
                on_conflict="email"
            )

        result = self.safe_execute(_call, DatabaseException, "Erro ao adicionar registro farm", email=email)
        
        if result:
            self.logger.sucesso(
                "Registro farm atualizado",
                email=email,
                pontos=pontos
            )
            return result
        else:
            self.logger.erro("Falha ao atualizar registro")
            return None
    
    def consultar_conta(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Consulta uma conta pelo email.
        
        Args:
            email: Email da conta
            
        Returns:
            Optional[Dict[str, Any]]: Dados da conta ou None
        """
        self.logger.debug(f"Consultando conta: {email}")
        
        def _call():
            return self._db_client.select_one(
                table=self.config.TABLE_CONTAS,
                filters={"email": email},
                columns="*"
            )
            
        result = self.safe_execute(_call, DatabaseException, "Erro ao consultar conta", email=email)
            
        if result:
            self.logger.info(f"Conta encontrada: {email}")
            return result
        else:
            self.logger.info(f"Nenhuma conta encontrada: {email}")
            return None
    
    def _validate_farm_input(self, email: str, pontos: int) -> None:
        """
        Valida entrada para registro de farm.
        
        Args:
            email: Email da conta
            pontos: Pontos obtidos
            
        Raises:
            ValidationException: Se entrada inválida
        """
        if not email or not isinstance(email, str):
            raise ValidationException(
                "Email inválido",
                details={"email": email}
            )
        
        if not isinstance(pontos, int) or pontos < 0:
            raise ValidationException(
                "Pontos inválidos",
                details={"pontos": pontos}
            )

    def listar_contas(self) -> Sequence[Dict[str, Any]]:
        """
        Lista todas as contas no banco.
        
        Returns:
            Sequence[Dict[str, Any]]: Lista de contas
        """
        self.logger.debug("Listando todas as contas")
        
        def _call():
            return self._db_client.select(
                table=self.config.TABLE_CONTAS,
                columns="*"
            )
            
        results = self.safe_execute(_call, DatabaseException, "Erro ao listar contas")
            
        if results:
            self.logger.info(f"Total de {len(results)} conta(s) encontrada(s)")
            return results
        else:
            self.logger.info("Nenhuma conta encontrada")
            return []
