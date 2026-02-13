"""
Interface para abstração de sistemas de arquivos.

Define o contrato que qualquer implementação de storage (Local, S3, Azure, etc.)
deve seguir para garantir desacoplamento completo.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from raxy.models import Conta


class IFileSystem(ABC):
    """
    Interface abstrata para operações de sistema de arquivos.
    
    Permite trocar entre filesystem local, cloud storage (S3, Azure),
    ou mock para testes sem modificar código cliente.
    
    Princípios:
    - Dependency Inversion Principle (DIP)
    - Open/Closed Principle (OCP)
    
    Benefícios:
    - Testabilidade: Mock em memória, sem I/O real
    - Cloud Migration: Troca Local → S3 sem reescrita
    - Portabilidade: Funciona em qualquer plataforma
    """
    
    # ========== Leitura ==========
    
    @abstractmethod
    def exists(self, path: str | Path) -> bool:
        """
        Verifica se arquivo/diretório existe.
        
        Args:
            path: Caminho do arquivo/diretório
            
        Returns:
            bool: True se existe
        """
        pass
    
    @abstractmethod
    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        """
        Lê conteúdo de arquivo texto.
        
        Args:
            path: Caminho do arquivo
            encoding: Codificação (padrão: utf-8)
            
        Returns:
            str: Conteúdo do arquivo
            
        Raises:
            FileNotFoundError: Se arquivo não existe
            IOError: Se erro ao ler
        """
        pass
    
    @abstractmethod
    def read_bytes(self, path: str | Path) -> bytes:
        """
        Lê conteúdo de arquivo binário.
        
        Args:
            path: Caminho do arquivo
            
        Returns:
            bytes: Conteúdo do arquivo
            
        Raises:
            FileNotFoundError: Se arquivo não existe
            IOError: Se erro ao ler
        """
        pass
    
    # ========== Escrita ==========
    
    @abstractmethod
    def write_text(
        self,
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True
    ) -> None:
        """
        Escreve conteúdo em arquivo texto.
        
        Args:
            path: Caminho do arquivo
            content: Conteúdo a escrever
            encoding: Codificação (padrão: utf-8)
            create_dirs: Se deve criar diretórios pais
            
        Raises:
            IOError: Se erro ao escrever
        """
        pass
    
    @abstractmethod
    def write_bytes(
        self,
        path: str | Path,
        content: bytes,
        create_dirs: bool = True
    ) -> None:
        """
        Escreve conteúdo em arquivo binário.
        
        Args:
            path: Caminho do arquivo
            content: Conteúdo a escrever
            create_dirs: Se deve criar diretórios pais
            
        Raises:
            IOError: Se erro ao escrever
        """
        pass
    
    # ========== Diretórios ==========
    
    @abstractmethod
    def mkdir(self, path: str | Path, parents: bool = True, exist_ok: bool = True) -> None:
        """
        Cria diretório.
        
        Args:
            path: Caminho do diretório
            parents: Se deve criar diretórios pais
            exist_ok: Se deve ignorar se já existe
            
        Raises:
            IOError: Se erro ao criar
        """
        pass
    
    @abstractmethod
    def list_dir(self, path: str | Path) -> List[str]:
        """
        Lista conteúdo de diretório.
        
        Args:
            path: Caminho do diretório
            
        Returns:
            List[str]: Lista de nomes de arquivos/diretórios
            
        Raises:
            FileNotFoundError: Se diretório não existe
            IOError: Se erro ao listar
        """
        pass
    
    # ========== Remoção ==========
    
    @abstractmethod
    def remove(self, path: str | Path) -> None:
        """
        Remove arquivo.
        
        Args:
            path: Caminho do arquivo
            
        Raises:
            FileNotFoundError: Se arquivo não existe
            IOError: Se erro ao remover
        """
        pass
    
    @abstractmethod
    def rmdir(self, path: str | Path, recursive: bool = False) -> None:
        """
        Remove diretório.
        
        Args:
            path: Caminho do diretório
            recursive: Se deve remover recursivamente
            
        Raises:
            FileNotFoundError: Se diretório não existe
            IOError: Se erro ao remover
        """
        pass
    
    # ========== Informações ==========
    
    @abstractmethod
    def get_size(self, path: str | Path) -> int:
        """
        Obtém tamanho do arquivo em bytes.
        
        Args:
            path: Caminho do arquivo
            
        Returns:
            int: Tamanho em bytes
            
        Raises:
            FileNotFoundError: Se arquivo não existe
        """
        pass
    
    @abstractmethod
    def is_file(self, path: str | Path) -> bool:
        """
        Verifica se é arquivo.
        
        Args:
            path: Caminho
            
        Returns:
            bool: True se é arquivo
        """
        pass
    
    @abstractmethod
    def is_dir(self, path: str | Path) -> bool:
        """
        Verifica se é diretório.
        
        Args:
            path: Caminho
            
        Returns:
            bool: True se é diretório
        """
        pass
    
    # ========== Utilitários ==========
    
    @abstractmethod
    def get_parent(self, path: str | Path) -> str:
        """
        Obtém diretório pai.
        
        Args:
            path: Caminho
            
        Returns:
            str: Caminho do diretório pai
        """
        pass
    
    @abstractmethod
    def join(self, *parts: str) -> str:
        """
        Junta partes de caminho.
        
        Args:
            *parts: Partes do caminho
            
        Returns:
            str: Caminho completo
        """
        pass

    # ========== Negócio (Helpers) ==========

    @abstractmethod
    def import_accounts_from_file(self, path: str | Path) -> List["Conta"]:
        """
        Lê e analisa um arquivo de texto contendo contas.

        Args:
            path: Caminho do arquivo a ser importado.

        Returns:
            Lista de objetos Conta analisados.
        """
        pass
