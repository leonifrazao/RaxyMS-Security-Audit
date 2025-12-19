"""
Implementação de repositório de contas em arquivo.
"""

from pathlib import Path
from typing import Sequence, Optional
import re

from raxy.core.interfaces import AccountRepository
from raxy.core.models import Conta
from raxy.core.exceptions import DataNotFoundException
from raxy.infrastructure.logging import get_logger

class FileAccountRepository(AccountRepository):
    """Repositório que lê contas de um arquivo de texto."""
    
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.logger = get_logger()

    def listar(self) -> Sequence[Conta]:
        """Lê contas do arquivo formatado user:pass."""
        if not self.file_path.exists():
            self.logger.aviso(f"Arquivo de contas não encontrado: {self.file_path}")
            return []
            
        contas = []
        try:
            content = self.file_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if not line or ":" not in line or line.startswith("#"):
                    continue
                
                parts = line.split(":", 1)
                if len(parts) == 2:
                    email, senha = parts[0].strip(), parts[1].strip()
                    # Gera ID de perfil seguro
                    safe_id = re.sub(r"[^a-z0-9]", "_", email.lower())
                    contas.append(Conta(email=email, senha=senha, id_perfil=safe_id))
                    
            self.logger.debug(f"Carregadas {len(contas)} contas de {self.file_path}")
            return contas
            
        except Exception as e:
            self.logger.erro(f"Erro ao ler arquivo de contas: {e}")
            return []

    def atualizar_pontos(self, email: str, pontos: int) -> bool:
        """
        Em arquivo texto simples, atualizar pontos é complexo/ineficiente.
        Geralmente apenas logamos ou usamos outro arquivo de 'state'.
        """
        self.logger.info(f"Persistência de pontos não implementada para arquivo texto ({email}: {pontos})")
        return True
