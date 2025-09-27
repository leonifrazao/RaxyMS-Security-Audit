"""Testes unitarios para utilitarios de perfil e user-agent."""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raxy.services.perfil_service import GerenciadorPerfil  # noqa: E402  pylint: disable=wrong-import-position


class TestGerenciadorPerfil(unittest.TestCase):
    """Garante que o gerenciador de perfis trata cenarios comuns corretamente."""

    @patch("raxy.services.perfil_service.Profiles.set_profile")
    @patch("raxy.services.perfil_service.UserAgent")
    @patch("raxy.services.perfil_service.Profiles.get_profile")
    def test_garantir_agente_usuario_cria_quando_inexistente(
        self,
        mock_get,
        mock_user_agent,
        mock_set,
    ) -> None:
        """Garante que um novo user-agent é criado e persistido quando ausente."""

        mock_get.return_value = None
        instancia_user_agent = mock_user_agent.return_value
        instancia_user_agent.get_random_user_agent.return_value = "UA-TESTE"

        gerenciador = GerenciadorPerfil()
        resultado = gerenciador.garantir_agente_usuario("perfil")

        self.assertEqual(resultado, "UA-TESTE")
        mock_set.assert_called_once()

    @patch("raxy.services.perfil_service.Profiles.get_profile")
    def test_garantir_agente_usuario_retorna_existente(self, mock_get) -> None:
        """Valida que o user-agent existente é reutilizado sem recriação."""

        mock_get.return_value = {"UA": "EXISTENTE"}
        gerenciador = GerenciadorPerfil()
        resultado = gerenciador.garantir_agente_usuario("perfil")
        self.assertEqual(resultado, "EXISTENTE")

    @patch("raxy.services.perfil_service.GerenciadorPerfil.garantir_agente_usuario", return_value="UA-ARGS")
    def test_argumentos_agente_usuario_encapsula_flag(self, mock_garantir) -> None:
        """Confirma que ``argumentos_agente_usuario`` monta a flag corretamente."""

        gerenciador = GerenciadorPerfil()
        argumentos = gerenciador.argumentos_agente_usuario("perfil")
        self.assertEqual(argumentos, ["--user-agent=UA-ARGS"])
        mock_garantir.assert_called_once_with(gerenciador, "perfil")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
