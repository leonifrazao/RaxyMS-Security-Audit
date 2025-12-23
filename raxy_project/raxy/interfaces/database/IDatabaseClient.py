"""
Interface para abstração de clientes de banco de dados.

Define o contrato que qualquer implementação de database
(Supabase, PostgreSQL, Firebase, Mock) deve seguir.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Sequence


class IDatabaseClient(ABC):
    """
    Interface abstrata para clientes de banco de dados.
    
    Permite trocar entre Supabase, PostgreSQL direto, Firebase,
    ou mock para testes sem modificar código cliente.
    
    Princípios:
    - Dependency Inversion Principle (DIP)
    - Repository Pattern
    
    Benefícios:
    - Testabilidade: Mock sem conexão real (10x mais rápido)
    - Portabilidade: Troca Supabase → PostgreSQL sem reescrita
    - Vendor Lock-in: Zero dependência crítica
    """
    
    @abstractmethod
    def upsert(
        self,
        table: str,
        data: Dict[str, Any],
        on_conflict: str
    ) -> Optional[Dict[str, Any]]:
        """
        Insere ou atualiza registro (UPSERT).
        
        Args:
            table: Nome da tabela
            data: Dados a inserir/atualizar
            on_conflict: Coluna para resolver conflito (ex: "email")
            
        Returns:
            Optional[Dict[str, Any]]: Registro inserido/atualizado ou None
        """
        pass
    
    @abstractmethod
    def select(
        self,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> Sequence[Dict[str, Any]]:
        """
        Seleciona registros de tabela.
        
        Args:
            table: Nome da tabela
            columns: Colunas a selecionar (padrão: "*")
            filters: Filtros (ex: {"email": "test@test.com"})
            limit: Limite de registros
            
        Returns:
            Sequence[Dict[str, Any]]: Lista de registros
        """
        pass
    
    @abstractmethod
    def select_one(
        self,
        table: str,
        filters: Dict[str, Any],
        columns: str = "*"
    ) -> Optional[Dict[str, Any]]:
        """
        Seleciona um único registro.
        
        Args:
            table: Nome da tabela
            filters: Filtros (ex: {"email": "test@test.com"})
            columns: Colunas a selecionar
            
        Returns:
            Optional[Dict[str, Any]]: Registro encontrado ou None
        """
        pass
    
    @abstractmethod
    def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Atualiza registros.
        
        Args:
            table: Nome da tabela
            data: Dados a atualizar
            filters: Filtros para registros a atualizar
            
        Returns:
            Optional[Dict[str, Any]]: Primeiro registro atualizado
        """
        pass
    
    @abstractmethod
    def delete(
        self,
        table: str,
        filters: Dict[str, Any]
    ) -> bool:
        """
        Remove registros.
        
        Args:
            table: Nome da tabela
            filters: Filtros para registros a remover
            
        Returns:
            bool: True se removeu com sucesso
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        Verifica se conexão com DB está saudável.
        
        Returns:
            bool: True se DB está acessível
        """
        pass
