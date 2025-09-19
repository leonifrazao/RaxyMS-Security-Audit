"""Utilitarios orientados a objeto para perfis e user-agent."""

from __future__ import annotations

from typing import ClassVar, List
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
    _PROVEDOR_USER_AGENT: ClassVar[UserAgent | None] = None

    @classmethod
    def garantir_agente_usuario(cls, perfil: str) -> str:
        """Garante a existência de um perfil com user-agent e o retorna.

        Args:
            perfil: Nome do perfil botasaurus que deve ser consultado/criado.

        Returns:
            ``str`` com o user-agent associado ao perfil fornecido.
        """

        perfil_existente = Profiles.get_profile(perfil)
        if perfil_existente:
            return perfil_existente["UA"]

        if cls._PROVEDOR_USER_AGENT is None:
            cls._PROVEDOR_USER_AGENT = UserAgent(
                limit=100,
                operating_systems=cls._SISTEMAS_OPERACIONAIS,
                software_names=cls._NOMES_SOFTWARE,
            )

        agente_usuario = cls._PROVEDOR_USER_AGENT.get_random_user_agent()

        Profiles.set_profile(perfil, {"UA": agente_usuario})
        return agente_usuario

    @classmethod
    def argumentos_agente_usuario(cls, perfil: str) -> List[str]:
        """Retorna a lista de argumentos ``add_arguments`` para o navegador.

        Args:
            perfil: Nome do perfil associado ao user-agent.

        Returns:
            Lista contendo a flag ``--user-agent=...``.
        """

        agente_usuario = cls.garantir_agente_usuario(perfil)
        return [f"--user-agent={agente_usuario}"]


__all__ = ["GerenciadorPerfil"]
