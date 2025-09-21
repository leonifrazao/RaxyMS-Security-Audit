"""Gerenciador de perfis e user-agent simples."""

from botasaurus.profiles import Profiles
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem


class GerenciadorPerfil:

    def __init__(self, perfil):
        self.provedor = UserAgent(
                limit=100,
                operating_systems=[
                    OperatingSystem.WINDOWS.value,
                    OperatingSystem.LINUX.value,
                    OperatingSystem.MACOS.value,
                ],
                software_names=[SoftwareName.EDGE.value],
            )
        self.perfil = perfil

    def agente_usuario(self):
        perfil_existente = Profiles.get_profile(self.perfil)
        if perfil_existente:
            return perfil_existente["UA"]

        agente = self.provedor.get_random_user_agent()
        Profiles.set_profile(self.perfil, {"UA": agente})
        return agente

    def argumentos(self):
        return [f"--user-agent={self.agente_usuario()}"]
