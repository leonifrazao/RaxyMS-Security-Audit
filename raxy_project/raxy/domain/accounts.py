"""Entidades relacionadas a contas."""

from __future__ import annotations

from dataclasses import dataclass

from raxy.proxy import Proxy  # sua implementação


@dataclass(frozen=True, slots=True)
class Conta:
    """Representa uma conta Microsoft Rewards."""

    email: str
    senha: str
    id_perfil: str
