"""Testes unitarios para utilitarios de perfil e user-agent."""

from __future__ import annotations

from json import JSONDecodeError
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raxy.core.profiles import GerenciadorPerfil  # noqa: E402  pylint: disable=wrong-import-position


class TestGerenciadorPerfil(unittest.TestCase):
    """Garante que o gerenciador de perfis trata cenarios comuns corretamente."""

    def setUp(self) -> None:  # noqa: D401 - comportamento padrao do unittest
        super().setUp()
        GerenciadorPerfil._PROVEDOR_USER_AGENT = None

    @patch("raxy.core.profiles.Profiles.set_profile")
    @patch("raxy.core.profiles.UserAgent")
    @patch("raxy.core.profiles.Profiles.get_profile")
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

        resultado = GerenciadorPerfil.garantir_agente_usuario("perfil")

        self.assertEqual(resultado, "UA-TESTE")
        mock_set.assert_called_once()

    @patch("raxy.core.profiles.Profiles.get_profile")
    def test_garantir_agente_usuario_retorna_existente(self, mock_get) -> None:
        """Valida que o user-agent existente é reutilizado sem recriação."""

        mock_get.return_value = {"UA": "EXISTENTE"}
        resultado = GerenciadorPerfil.garantir_agente_usuario("perfil")
        self.assertEqual(resultado, "EXISTENTE")

    @patch("raxy.core.profiles.GerenciadorPerfil._sanear_arquivo_perfis")
    @patch("raxy.core.profiles.Profiles.set_profile")
    @patch("raxy.core.profiles.UserAgent")
    @patch("raxy.core.profiles.Profiles.get_profile")
    def test_garantir_agente_usuario_salva_apos_saneamento(
        self,
        mock_get,
        mock_user_agent,
        mock_set,
        mock_sanear,
    ) -> None:
        """O arquivo de perfis deve ser saneado quando o salvamento falha."""

        mock_get.return_value = None
        instancia_user_agent = mock_user_agent.return_value
        instancia_user_agent.get_random_user_agent.return_value = "UA-NOVO"
        erro = JSONDecodeError("msg", "", 0)
        mock_set.side_effect = [erro, None]

        resultado = GerenciadorPerfil.garantir_agente_usuario("perfil")

        self.assertEqual(resultado, "UA-NOVO")
        self.assertEqual(mock_set.call_count, 2)
        mock_sanear.assert_called_once()

    @patch("raxy.core.profiles.GerenciadorPerfil._sanear_arquivo_perfis")
    @patch("raxy.core.profiles.Profiles.set_profile")
    @patch("raxy.core.profiles.UserAgent")
    @patch("raxy.core.profiles.Profiles.get_profile")
    def test_garantir_agente_usuario_recupera_json_corrompido(
        self,
        mock_get,
        mock_user_agent,
        mock_set,
        mock_sanear,
    ) -> None:
        """Ao encontrar JSON inválido o gerenciador deve recarregar o arquivo."""

        erro = JSONDecodeError("msg", "", 0)
        mock_get.side_effect = [erro, {"UA": "EXISTE"}]

        resultado = GerenciadorPerfil.garantir_agente_usuario("perfil")

        self.assertEqual(resultado, "EXISTE")
        mock_sanear.assert_called_once()
        mock_set.assert_not_called()
        mock_user_agent.assert_not_called()

    @patch("raxy.core.profiles.GerenciadorPerfil.garantir_agente_usuario", return_value="UA-ARGS")
    def test_argumentos_agente_usuario_encapsula_flag(self, mock_garantir) -> None:
        """Confirma que ``argumentos_agente_usuario`` monta a flag corretamente."""

        argumentos = GerenciadorPerfil.argumentos_agente_usuario("perfil")
        self.assertEqual(argumentos, ["--user-agent=UA-ARGS"])
        mock_garantir.assert_called_once_with("perfil")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
