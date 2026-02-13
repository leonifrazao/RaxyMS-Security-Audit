"""
Mock FileSystem para testes unitários.

Implementação em memória que não toca o disco real,
permitindo testes rápidos e isolados.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Union, TYPE_CHECKING

from raxy.interfaces.database import IFileSystem
if TYPE_CHECKING:
    from raxy.models import Conta


class MockFileSystem(IFileSystem):
    """
    FileSystem mock em memória para testes.
    
    Armazena todos os arquivos em dicionário Python,
    sem tocar o filesystem real.
    
    Design Pattern: Test Double (Mock Object)
    Uso: Testes unitários
    
    Benefícios:
    - Execução instantânea (<1ms)
    - Zero I/O real
    - Determinístico
    - Isolamento perfeito entre testes
    """
    
    def __init__(self):
        """Inicializa filesystem mock."""
        self._files: Dict[str, Union[str, bytes]] = {}
        self._dirs: set[str] = {"/"}
    
    def _normalize_path(self, path: str | Path) -> str:
        """
        Normaliza caminho.
        
        Args:
            path: Caminho a normalizar
            
        Returns:
            str: Caminho normalizado
        """
        p = str(path).replace("\\", "/")
        if not p.startswith("/"):
            p = "/" + p
        return p
    
    # ========== Leitura ==========
    
    def exists(self, path: str | Path) -> bool:
        """Verifica se arquivo/diretório existe."""
        norm = self._normalize_path(path)
        return norm in self._files or norm in self._dirs
    
    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        """Lê conteúdo de arquivo texto."""
        norm = self._normalize_path(path)
        
        if norm not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        
        content = self._files[norm]
        
        if isinstance(content, bytes):
            return content.decode(encoding)
        return content
    
    def read_bytes(self, path: str | Path) -> bytes:
        """Lê conteúdo de arquivo binário."""
        norm = self._normalize_path(path)
        
        if norm not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        
        content = self._files[norm]
        
        if isinstance(content, str):
            return content.encode("utf-8")
        return content
    
    # ========== Escrita ==========
    
    def write_text(
        self,
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True
    ) -> None:
        """Escreve conteúdo em arquivo texto."""
        norm = self._normalize_path(path)
        
        if create_dirs:
            parent = self.get_parent(norm)
            if parent != "/":
                self._ensure_dir_exists(parent)
        
        self._files[norm] = content
    
    def write_bytes(
        self,
        path: str | Path,
        content: bytes,
        create_dirs: bool = True
    ) -> None:
        """Escreve conteúdo em arquivo binário."""
        norm = self._normalize_path(path)
        
        if create_dirs:
            parent = self.get_parent(norm)
            if parent != "/":
                self._ensure_dir_exists(parent)
        
        self._files[norm] = content
    
    # ========== Diretórios ==========
    
    def mkdir(self, path: str | Path, parents: bool = True, exist_ok: bool = True) -> None:
        """Cria diretório."""
        norm = self._normalize_path(path)
        
        if norm in self._dirs:
            if not exist_ok:
                raise FileExistsError(f"Directory already exists: {path}")
            return
        
        if parents:
            self._ensure_dir_exists(norm)
        else:
            parent = self.get_parent(norm)
            if parent not in self._dirs:
                raise FileNotFoundError(f"Parent directory does not exist: {parent}")
            self._dirs.add(norm)
    
    def _ensure_dir_exists(self, path: str) -> None:
        """Garante que diretório e pais existam."""
        parts = path.strip("/").split("/")
        current = ""
        
        for part in parts:
            if not part:
                continue
            current += "/" + part
            self._dirs.add(current)
    
    def list_dir(self, path: str | Path) -> List[str]:
        """Lista conteúdo de diretório."""
        norm = self._normalize_path(path)
        
        if norm not in self._dirs:
            raise FileNotFoundError(f"Directory not found: {path}")
        
        items = set()
        prefix = norm.rstrip("/") + "/"
        
        # Lista arquivos
        for file_path in self._files:
            if file_path.startswith(prefix):
                rel = file_path[len(prefix):]
                if "/" not in rel:  # Apenas itens diretos
                    items.add(rel)
        
        # Lista subdiretórios
        for dir_path in self._dirs:
            if dir_path != norm and dir_path.startswith(prefix):
                rel = dir_path[len(prefix):]
                if "/" not in rel.rstrip("/"):  # Apenas itens diretos
                    items.add(rel.split("/")[0])
        
        return sorted(items)
    
    # ========== Remoção ==========
    
    def remove(self, path: str | Path) -> None:
        """Remove arquivo."""
        norm = self._normalize_path(path)
        
        if norm not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        
        del self._files[norm]
    
    def rmdir(self, path: str | Path, recursive: bool = False) -> None:
        """Remove diretório."""
        norm = self._normalize_path(path)
        
        if norm not in self._dirs:
            raise FileNotFoundError(f"Directory not found: {path}")
        
        if recursive:
            # Remove todos os arquivos e subdiretórios
            prefix = norm.rstrip("/") + "/"
            
            files_to_remove = [f for f in self._files if f.startswith(prefix)]
            for f in files_to_remove:
                del self._files[f]
            
            dirs_to_remove = [d for d in self._dirs if d.startswith(prefix) or d == norm]
            for d in dirs_to_remove:
                self._dirs.discard(d)
        else:
            # Verifica se está vazio
            if any(f.startswith(norm.rstrip("/") + "/") for f in self._files):
                raise OSError(f"Directory not empty: {path}")
            if any(d.startswith(norm.rstrip("/") + "/") for d in self._dirs if d != norm):
                raise OSError(f"Directory not empty: {path}")
            
            self._dirs.discard(norm)
    
    # ========== Informações ==========
    
    def get_size(self, path: str | Path) -> int:
        """Obtém tamanho do arquivo em bytes."""
        norm = self._normalize_path(path)
        
        if norm not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        
        content = self._files[norm]
        if isinstance(content, str):
            return len(content.encode("utf-8"))
        return len(content)
    
    def is_file(self, path: str | Path) -> bool:
        """Verifica se é arquivo."""
        norm = self._normalize_path(path)
        return norm in self._files
    
    def is_dir(self, path: str | Path) -> bool:
        """Verifica se é diretório."""
        norm = self._normalize_path(path)
        return norm in self._dirs
    
    # ========== Utilitários ==========
    
    def get_parent(self, path: str | Path) -> str:
        """Obtém diretório pai."""
        norm = self._normalize_path(path)
        parts = norm.rstrip("/").split("/")
        if len(parts) <= 1:
            return "/"
        return "/".join(parts[:-1]) or "/"
    
    def join(self, *parts: str) -> str:
        """Junta partes de caminho."""
        return "/" + "/".join(p.strip("/") for p in parts if p)
    
    # ========== Métodos de Teste ==========
    
    def clear(self) -> None:
        """Limpa todos os arquivos (útil para testes)."""
        self._files.clear()
        self._dirs = {"/"}
    
    def get_all_files(self) -> Dict[str, Union[str, bytes]]:
        """Retorna todos os arquivos (útil para debugging)."""
        return self._files.copy()
    
    def get_all_dirs(self) -> List[str]:
        """Retorna todos os diretórios (útil para debugging)."""
        return list(self._dirs)

    def import_accounts_from_file(self, path: str | Path) -> List["Conta"]:
        """
        Mock da importação de contas.
        Retorna lista vazia por padrão, ou poderia ser mockado para retornar dados.
        """
        # Se o arquivo existe e tem conteúdo, poderíamos tentar parsear
        # Mas para mock simples, retornamos vazio ou erro se não existir
        if not self.exists(path):
            from raxy.core.exceptions import DataNotFoundException
            raise DataNotFoundException(f"Arquivo não encontrado no mock: {path}")
        return [].copy()
