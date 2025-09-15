"""Testes unitarios para o orquestrador principal."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import ExecutorEmLote  # noqa: E402  pylint: disable=wrong-import-position
from src.contas import carregar_contas  # noqa: E402  pylint: disable=wrong-import-position


class TestExecutorEmLote(unittest.TestCase):
    """Cobertura dos metodos puros de normalizacao e carregamento."""

    def test_normalizar_acoes_remove_espacos_e_minusculas(self) -> None:
        resultado = ExecutorEmLote._normalizar_acoes([" Login ", "REWARDS", " "])
        self.assertEqual(resultado, ["login", "rewards"])

    def test_carregar_contas_lida_com_linhas_invalidas(self) -> None:
        conteudo = """
            # comentario
            user1@example.com:senha1
            invalido_sem_senha

            user2@example.com : senha2
        """
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as tmp:
            tmp.write(conteudo)
            tmp_path = tmp.name

        try:
            contas = carregar_contas(tmp_path)
        finally:
            pathlib.Path(tmp_path).unlink(missing_ok=True)

        emails = [conta.email for conta in contas]
        self.assertEqual(emails, ["user1@example.com", "user2@example.com"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
