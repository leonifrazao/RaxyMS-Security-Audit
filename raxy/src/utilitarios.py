"""Utilitarios orientados a objeto para perfis e user-agent."""

from typing import List
from botasaurus.profiles import Profiles
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem


class GerenciadorPerfil:
    """Responsavel por garantir perfis e montar argumentos de navegadores."""

    _NOMES_SOFTWARE = [SoftwareName.EDGE.value]
    _SISTEMAS_OPERACIONAIS = [
        OperatingSystem.WINDOWS.value,
        OperatingSystem.LINUX.value,
        OperatingSystem.CHROMEOS.value,
        OperatingSystem.MACOS.value,
    ]

    @classmethod
    def garantir_agente_usuario(cls, perfil: str) -> str:
        """Garante a existencia de um perfil com user-agent e o retorna."""

        perfil_existente = Profiles.get_profile(perfil)
        if perfil_existente:
            return perfil_existente["UA"]

        agente_usuario = UserAgent(
            limit=100,
            operating_systems=cls._SISTEMAS_OPERACIONAIS,
            software_names=cls._NOMES_SOFTWARE,
        ).get_random_user_agent()

        Profiles.set_profile(perfil, {"UA": agente_usuario})
        return agente_usuario

    @classmethod
    def argumentos_agente_usuario(cls, perfil: str) -> List[str]:
        """Retorna a lista de argumentos `add_arguments` para o navegador."""

        agente_usuario = cls.garantir_agente_usuario(perfil)
        return [f"--user-agent={agente_usuario}"]


__all__ = ["GerenciadorPerfil"]
