"""Testes unitarios para o modulo de autenticacao."""

from __future__ import annotations

import pathlib
import sys
import unittest

# Garante que ``src`` esta no path ao rodar ``python -m unittest`` a partir da raiz
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.autenticacao import AutenticadorRewards, CredenciaisInvalidas  # noqa: E402  pylint: disable=wrong-import-position


class TestAutenticadorRewards(unittest.TestCase):
    """Garante que a validacao de credenciais cobre os cenarios esperados."""

    def test_validar_credenciais_retorna_email_normalizado(self) -> None:
        email, senha = AutenticadorRewards.validar_credenciais("  user@example.com  ", "  segredo  ")
        self.assertEqual(email, "user@example.com")
        self.assertEqual(senha, "segredo")

    def test_validar_credenciais_rejeita_email_invalido(self) -> None:
        with self.assertRaises(CredenciaisInvalidas):
            AutenticadorRewards.validar_credenciais("email_invalido", "senha")

    def test_validar_credenciais_rejeita_senha_vazia(self) -> None:
        with self.assertRaises(CredenciaisInvalidas):
            AutenticadorRewards.validar_credenciais("user@example.com", "   ")

    def test_validar_credenciais_rejeita_email_vazio(self) -> None:
        with self.assertRaises(CredenciaisInvalidas):
            AutenticadorRewards.validar_credenciais("   ", "segredo")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
