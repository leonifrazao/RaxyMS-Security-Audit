"""Utilitarios orientados a objeto para perfis e user-agent."""

from __future__ import annotations

from json import JSONDecodeError
from pathlib import Path
from typing import ClassVar, List, Mapping, MutableMapping

from botasaurus.profiles import Profiles
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import OperatingSystem, SoftwareName

from .logging import log


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

    @staticmethod
    def _sanear_arquivo_perfis() -> None:
        """Recria o arquivo JSON de perfis quando estiver corrompido."""

        backend = Profiles.storage_backend_instance
        caminho = getattr(backend, "json_path", None)
        if caminho:
            caminho_path = Path(str(caminho))
            try:
                caminho_path.parent.mkdir(parents=True, exist_ok=True)
                caminho_path.write_text("{}", encoding="utf-8")
            except Exception as exc:  # pragma: no cover - ambiente de arquivo externo
                log.debug(
                    "Falha ao reescrever arquivo de perfis do botasaurus",
                    detalhe=str(exc),
                )

        try:
            backend.json_data = {}
        except Exception:  # pragma: no cover - atributo interno pode nao existir
            setattr(backend, "json_data", {})

        try:
            backend.commit_to_disk()
        except Exception as exc:  # pragma: no cover - escrita depende do ambiente
            log.debug(
                "Nao foi possivel salvar arquivo de perfis apos saneamento",
                detalhe=str(exc),
            )

    @classmethod
    def _carregar_perfil(cls, perfil: str) -> MutableMapping[str, str] | None:
        """Obtém o perfil existente tratando corrupções comuns do JSON."""

        try:
            return Profiles.get_profile(perfil)
        except JSONDecodeError as exc:
            log.aviso(
                "Arquivo de perfis do botasaurus corrompido; recriando",
                perfil=perfil,
                detalhe=str(exc),
            )
            cls._sanear_arquivo_perfis()
            try:
                return Profiles.get_profile(perfil)
            except JSONDecodeError as exc_retentativa:
                log.aviso(
                    "Falha ao recarregar perfis do botasaurus apos saneamento",
                    perfil=perfil,
                    detalhe=str(exc_retentativa),
                )
            except OSError as exc_retentativa:
                log.aviso(
                    "Erro de E/S ao recarregar perfis do botasaurus",
                    perfil=perfil,
                    detalhe=str(exc_retentativa),
                )
        except OSError as exc:
            log.aviso(
                "Erro de E/S ao carregar perfis do botasaurus",
                perfil=perfil,
                detalhe=str(exc),
            )
        return None

    @classmethod
    def _persistir_agente_usuario(cls, perfil: str, agente_usuario: str) -> None:
        """Persiste o user-agent recém-gerado tratando corrupções no arquivo."""

        try:
            Profiles.set_profile(perfil, {"UA": agente_usuario})
        except JSONDecodeError as exc:
            log.aviso(
                "Arquivo de perfis do botasaurus corrompido ao salvar; tentando novamente",
                perfil=perfil,
                detalhe=str(exc),
            )
            cls._sanear_arquivo_perfis()
            try:
                Profiles.set_profile(perfil, {"UA": agente_usuario})
            except (JSONDecodeError, OSError) as exc_final:
                log.aviso(
                    "Nao foi possivel persistir user-agent do botasaurus",
                    perfil=perfil,
                    detalhe=str(exc_final),
                )
        except OSError as exc:
            log.aviso(
                "Erro de E/S ao salvar user-agent no botasaurus",
                perfil=perfil,
                detalhe=str(exc),
            )

    @classmethod
    def garantir_agente_usuario(cls, perfil: str) -> str:
        """Garante a existência de um perfil com user-agent e o retorna.

        Args:
            perfil: Nome do perfil botasaurus que deve ser consultado/criado.

        Returns:
            ``str`` com o user-agent associado ao perfil fornecido.
        """

        perfil_existente: Mapping[str, str] | None = cls._carregar_perfil(perfil)
        if perfil_existente and perfil_existente.get("UA"):
            return perfil_existente["UA"]

        if cls._PROVEDOR_USER_AGENT is None:
            cls._PROVEDOR_USER_AGENT = UserAgent(
                limit=100,
                operating_systems=cls._SISTEMAS_OPERACIONAIS,
                software_names=cls._NOMES_SOFTWARE,
            )

        agente_usuario = cls._PROVEDOR_USER_AGENT.get_random_user_agent()

        cls._persistir_agente_usuario(perfil, agente_usuario)
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
