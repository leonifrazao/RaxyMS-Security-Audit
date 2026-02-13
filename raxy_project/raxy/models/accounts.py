"""Entidades relacionadas a contas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from raxy.infrastructure.proxy import Proxy  # sua implementação


@dataclass(frozen=True, slots=True)
class Conta:
    """Representa uma conta Microsoft Rewards."""

    email: str
    senha: str = ""  # Senha pode não vir do banco de dados de farm
    id_perfil: str = "" # Pode ser opcional
    email_backup: str = ""  # NOVO: Email de recuperação
    senha_email_backup: str = ""  # NOVO: Senha do email de recuperação
    pontos: int = 0
    ultima_farm: Optional[str] = None
    proxy: Optional[Proxy] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> Conta:
        """Cria uma instância de Conta a partir de um dicionário."""
        return cls(
            email=data.get("email", ""),
            senha=data.get("senha", ""),
            id_perfil=data.get("id_perfil", ""),
            email_backup=data.get("email_backup", ""),
            senha_email_backup=data.get("senha_email_backup", ""),
            pontos=data.get("pontos", 0),
            ultima_farm=data.get("ultima_farm"),
            # Proxy precisaria de mais lógica se viesse do dict, por enquanto ignora ou implementa se necessário
        )

    def to_dict(self) -> dict:
        """Converte o objeto para dicionário."""
        return {
            "email": self.email,
            "senha": self.senha,
            "id_perfil": self.id_perfil,
            "email_backup": self.email_backup,
            "senha_email_backup": self.senha_email_backup,
            "pontos": self.pontos,
            "ultima_farm": self.ultima_farm,
            "proxy": self.proxy.uri if self.proxy else None
        }
