"""Contrato para gerenciamento de perfis e user-agent."""

from __future__ import annotations

from abc import ABC, abstractmethod


class IPerfilService(ABC):
    """Garante isolamento e user-agent por perfil de navegação."""

    @abstractmethod
    def argumentos_agente_usuario(self, perfil: str) -> list[str]:
        """Retorna os argumentos de linha de comando para o navegador."""
        
    @abstractmethod
    def garantir_perfil(self, perfil: str, email: str, senha: str) -> None:
        """Garante que o perfil exista."""
