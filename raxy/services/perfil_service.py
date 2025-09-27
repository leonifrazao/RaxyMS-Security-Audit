"""Gerenciamento de perfis e user-agents."""

from __future__ import annotations

from random_user_agent.params import OperatingSystem, SoftwareName
from random_user_agent.user_agent import UserAgent
from botasaurus.profiles import Profiles


from interfaces.services import IPerfilService

class GerenciadorPerfil(IPerfilService):
    """Centraliza a criação e persistência de user-agents por perfil."""

    _SOFTWARES_PADRAO = [SoftwareName.EDGE.value]
    _SISTEMAS_PADRAO = [
        OperatingSystem.WINDOWS.value,
        OperatingSystem.LINUX.value,
        OperatingSystem.MACOS.value,
    ]

    def __init__(self) -> None:
        self._provedor = UserAgent(
            limit=100,
            software_names=self._SOFTWARES_PADRAO,
            operating_systems=self._SISTEMAS_PADRAO,
        )

    def garantir_agente_usuario(self, perfil: str) -> str:
        """Retorna o user-agent associado ao perfil, criando se necessário."""

        if not perfil:
            raise ValueError("Perfil deve ser informado")

        existente = Profiles.get_profile(perfil)
        if existente and existente.get("UA"):
            return existente["UA"]

        agente = self._provedor.get_random_user_agent()
        Profiles.set_profile(perfil, {"UA": agente})
        return agente

    def argumentos_agente_usuario(self, perfil: str) -> list[str]:
        """Retorna a flag de linha de comando para o user-agent do perfil."""

        agente = self.garantir_agente_usuario(perfil)
        return [f"--user-agent={agente}"]


__all__ = ["GerenciadorPerfil"]
