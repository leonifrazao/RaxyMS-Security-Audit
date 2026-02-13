"""
Implementação do IFileSystem usando sistema de arquivos local.

Adapter para pathlib.Path que implementa a interface IFileSystem.
"""

from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import List

from raxy.interfaces.database import IFileSystem
from raxy.models import Conta
from raxy.core.logging import get_logger
from raxy.core.exceptions import DataValidationException, FileRepositoryException, DataNotFoundException, wrap_exception
import re


class LocalFileSystem(IFileSystem):
    """
    Implementação do IFileSystem usando filesystem local.
    
    Adapter para pathlib.Path que segue a interface padronizada,
    permitindo trocar para cloud storage sem impacto no código cliente.
    
    Design Pattern: Adapter Pattern
    Princípio: Dependency Inversion Principle (DIP)
    """
    
    def __init__(self, base_path: str | Path | None = None):
        """
        Inicializa o filesystem local.
        
        Args:
            base_path: Caminho base opcional (todos os paths serão relativos a este)
        """
        self._base_path = Path(base_path) if base_path else None
    
    def _resolve_path(self, path: str | Path) -> Path:
        """
        Resolve caminho completo.
        
        Args:
            path: Caminho relativo ou absoluto
            
        Returns:
            Path: Caminho absoluto resolvido
        """
        p = Path(path)
        if self._base_path and not p.is_absolute():
            return self._base_path / p
        return p
    
    # ========== Leitura ==========
    
    def exists(self, path: str | Path) -> bool:
        """Verifica se arquivo/diretório existe."""
        return self._resolve_path(path).exists()
    
    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        """Lê conteúdo de arquivo texto."""
        return self._resolve_path(path).read_text(encoding=encoding)
    
    def read_bytes(self, path: str | Path) -> bytes:
        """Lê conteúdo de arquivo binário."""
        return self._resolve_path(path).read_bytes()
    
    # ========== Escrita ==========
    
    def write_text(
        self,
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True
    ) -> None:
        """Escreve conteúdo em arquivo texto."""
        resolved = self._resolve_path(path)
        
        if create_dirs:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        
        resolved.write_text(content, encoding=encoding)
    
    def write_bytes(
        self,
        path: str | Path,
        content: bytes,
        create_dirs: bool = True
    ) -> None:
        """Escreve conteúdo em arquivo binário."""
        resolved = self._resolve_path(path)
        
        if create_dirs:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        
        resolved.write_bytes(content)
    
    # ========== Diretórios ==========
    
    def mkdir(self, path: str | Path, parents: bool = True, exist_ok: bool = True) -> None:
        """Cria diretório."""
        self._resolve_path(path).mkdir(parents=parents, exist_ok=exist_ok)
    
    def list_dir(self, path: str | Path) -> List[str]:
        """Lista conteúdo de diretório."""
        resolved = self._resolve_path(path)
        return [item.name for item in resolved.iterdir()]
    
    # ========== Remoção ==========
    
    def remove(self, path: str | Path) -> None:
        """Remove arquivo."""
        self._resolve_path(path).unlink()
    
    def rmdir(self, path: str | Path, recursive: bool = False) -> None:
        """Remove diretório."""
        resolved = self._resolve_path(path)
        
        if recursive:
            shutil.rmtree(resolved)
        else:
            resolved.rmdir()
    
    # ========== Informações ==========
    
    def get_size(self, path: str | Path) -> int:
        """Obtém tamanho do arquivo em bytes."""
        return self._resolve_path(path).stat().st_size
    
    def is_file(self, path: str | Path) -> bool:
        """Verifica se é arquivo."""
        return self._resolve_path(path).is_file()
    
    def is_dir(self, path: str | Path) -> bool:
        """Verifica se é diretório."""
        return self._resolve_path(path).is_dir()
    
    # ========== Utilitários ==========
    
    def get_parent(self, path: str | Path) -> str:
        """Obtém diretório pai."""
        return str(self._resolve_path(path).parent)
    
    def join(self, *parts: str) -> str:
        """Junta partes de caminho."""
        if self._base_path:
            return str(self._base_path.joinpath(*parts))
        return str(Path(*parts))

    def import_accounts_from_file(self, path: str | Path) -> List[Conta]:
        """
        Lê e analisa um arquivo de texto contendo contas (email:senha).
        
        Args:
            path: Caminho do arquivo a ser importado.
            
        Returns:
            Lista de objetos Conta analisados.
        """
        caminho = str(path)
        if not self.exists(caminho):
             raise DataNotFoundException(f"Arquivo não encontrado: {caminho}", details={"path": caminho})

        logger = get_logger()
        logger.debug(f"Importando contas de: {caminho}")

        try:
            content = self.read_text(caminho)
        except Exception as e:
            raise wrap_exception(e, FileRepositoryException, "Erro ao ler arquivo de importação", path=caminho)

        contas = []
        for i, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue

            try:
                parts = line.split(":", 1)
                email = parts[0].strip()
                senha = parts[1].strip()

                if "@" not in email:
                     logger.aviso(f"Linha {i}: Email inválido ignorado ({email})")
                     continue

                # Gera ID de perfil baseado no email se não existir lógica melhor
                base = email.lower().replace("@", "_at_")
                id_perfil = re.sub(r"[^a-z0-9._-]+", "_", base).strip("_")

                contas.append(Conta(email=email, senha=senha, id_perfil=id_perfil))
            except Exception as e:
                logger.aviso(f"Linha {i}: Erro ao processar conta", erro=str(e))

        logger.info(f"Importação concluída. {len(contas)} contas analisadas.")
        return contas
