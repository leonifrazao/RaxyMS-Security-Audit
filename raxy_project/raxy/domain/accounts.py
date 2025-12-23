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
            pontos=data.get("pontos", 0),
            ultima_farm=data.get("ultima_farm"),
            # Proxy precisaria de mais lógica se viesse do dict, por enquanto ignora ou implementa se necessário
        )
