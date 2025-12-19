"""
Entidades relacionadas a contas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Conta:
    """Representa uma conta Microsoft Rewards (Imutável)."""

    email: str
    senha: str
    id_perfil: Optional[str] = None
    
    def __post_init__(self):
        if not self.id_perfil:
            # Hack para permitir atribuição em frozen dataclass
            object.__setattr__(self, 'id_perfil', self.email)

    @property
    def is_valid(self) -> bool:
        return "@" in self.email and len(self.senha) > 0
