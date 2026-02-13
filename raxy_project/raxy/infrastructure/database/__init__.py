"""
Infraestrutura de persistência (Banco de Dados e Sistema de Arquivos).
"""

from .mock_database import MockDatabaseClient
from .sqlite import SQLiteRepository
from .supabase import SupabaseRepository, SupabaseDatabaseClient
from .local_filesystem import LocalFileSystem
from .mock_filesystem import MockFileSystem

__all__ = [
    "SupabaseDatabaseClient",
    "MockDatabaseClient",
    "SQLiteRepository",
    "SupabaseRepository",
    "LocalFileSystem",
    "MockFileSystem",
]
