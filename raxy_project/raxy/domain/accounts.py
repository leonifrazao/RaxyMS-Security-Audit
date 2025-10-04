"""Entidades relacionadas a contas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Conta:
    """Representa uma conta Microsoft Rewards."""

    email: str
    senha: str
    id_perfil: str
    proxy: str
