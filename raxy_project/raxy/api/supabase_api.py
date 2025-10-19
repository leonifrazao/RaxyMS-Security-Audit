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

from raxy.interfaces.repositories import IDatabaseRepository
from raxy.interfaces.services import ILoggingService
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


class SupabaseRepository(IDatabaseRepository):
    """
    Repositório de banco de dados usando Supabase.
    
    Implementa a interface IDatabaseRepository com Supabase,
    fornecendo acesso estruturado ao banco de dados.
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        logger: Optional[ILoggingService] = None
    ):
        """
        Inicializa o repositório.
        
        Args:
            url: URL do Supabase (opcional, usa env se não fornecido)
            key: Chave do Supabase (opcional, usa env se não fornecido)
            logger: Serviço de logging
        """
        self._logger = logger or self._get_default_logger()
        self.config = SupabaseConfig()
        
        # Obtém credenciais
        if not url or not key:
            url, key = self.config.from_env()
        
        # Inicializa cliente
        self._initialize_client(url, key)
    
    def _get_default_logger(self) -> ILoggingService:
        """Obtém logger padrão."""
        from raxy.core.logging import get_logger
        return get_logger()
    
    def _initialize_client(self, url: str, key: str) -> None:
        """
        Inicializa o cliente Supabase.
        
        Args:
            url: URL do Supabase
            key: Chave de API
            
        Raises:
            DatabaseException: Se erro ao conectar
        """
        try:
            self.supabase: Client = create_client(url, key)
            self._logger.info("Cliente Supabase inicializado com sucesso")
        except Exception as e:
            self._logger.erro("Falha ao criar cliente Supabase", exception=e)
            raise wrap_exception(
                e, DatabaseException,
                "Erro ao conectar com Supabase"
            )

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
        
        self._logger.info(
            "Adicionando/atualizando registro de farm",
            email=email,
            pontos=pontos
        )
        
        try:
            # Prepara dados
            timestamp = datetime.now(timezone.utc).isoformat()
            data = {
                "email": email,
                "pontos": pontos,
                "ultima_farm": timestamp,
            }
            
            # Operação upsert (insert ou update)
            response = self.supabase.table(self.config.TABLE_CONTAS).upsert(
                data,
                on_conflict="email"
            ).execute()
            
            if response.data:
                self._logger.sucesso(
                    "Registro farm atualizado",
                    email=email,
                    pontos=pontos
                )
                return response.data[0] if response.data else None
            else:
                self._logger.erro(
                    "Falha ao atualizar registro",
                    error=getattr(response, "error", None)
                )
                return None
                
        except Exception as e:
            self._logger.erro(
                "Erro ao adicionar registro farm",
                exception=e,
                email=email
            )
            return None
    
    def consultar_conta(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Consulta uma conta pelo email.
        
        Args:
            email: Email da conta
            
        Returns:
            Optional[Dict[str, Any]]: Dados da conta ou None
        """
        self._logger.debug(f"Consultando conta: {email}")
        
        try:
            response = (
                self.supabase.table(self.config.TABLE_CONTAS)
                .select("*")
                .eq("email", email)
                .limit(1)
                .execute()
            )
            
            if response.data:
                self._logger.info(f"Conta encontrada: {email}")
                return response.data[0]
            else:
                self._logger.info(f"Nenhuma conta encontrada: {email}")
                return None
                
        except Exception as e:
            self._logger.erro(
                "Erro ao consultar conta",
                exception=e,
                email=email
            )
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
        self._logger.debug("Listando todas as contas")
        
        try:
            response = self.supabase.table(self.config.TABLE_CONTAS).select("*").execute()
            
            if response.data:
                self._logger.info(f"Total de {len(response.data)} conta(s) encontrada(s)")
                return response.data
            else:
                self._logger.info("Nenhuma conta encontrada")
                return []
                
        except Exception as e:
            self._logger.erro(
                "Erro ao listar contas",
                exception=e,
                details={"error": getattr(e, "error", None)}
            )
            return []
