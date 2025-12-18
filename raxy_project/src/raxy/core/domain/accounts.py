"""Entidades relacionadas a contas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Conta:
    """Representa uma conta Microsoft Rewards."""

    email: str
    senha: str
    id_perfil: Optional[str] = None
    
    def __post_init__(self):
        if not self.id_perfil:
            # Hack para permitir atribuição em frozen dataclass durante init
            object.__setattr__(self, 'id_perfil', self.email)
