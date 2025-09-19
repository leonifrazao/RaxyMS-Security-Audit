"""Testes unitarios para o orquestrador principal."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raxy import ExecutorEmLote  # noqa: E402  pylint: disable=wrong-import-position
from raxy.core.accounts import carregar_contas  # noqa: E402  pylint: disable=wrong-import-position


class TestExecutorEmLote(unittest.TestCase):
    """Cobertura dos metodos puros de normalizacao e carregamento."""

    def test_normalizar_acoes_remove_espacos_e_minusculas(self) -> None:
        """Verifica se `_normalizar_acoes` remove espaços e converte para minúsculo."""

        resultado = ExecutorEmLote._normalizar_acoes([" Login ", "REWARDS", " "])
        self.assertEqual(resultado, ["login", "rewards"])

    def test_carregar_contas_lida_com_linhas_invalidas(self) -> None:
        """Garante que `carregar_contas` ignore linhas inválidas e comentários."""

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

    def test_carregar_contas_gera_identificadores_unicos(self) -> None:
        """Perfis derivados do email devem permanecer únicos após sanitização."""

        conteudo = """
            user@example.com:senha1
            user@outro.com:senha2
            user+alias@example.com:senha3
        """

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as tmp:
            tmp.write(conteudo)
            tmp_path = tmp.name

        try:
            contas = carregar_contas(tmp_path)
        finally:
            pathlib.Path(tmp_path).unlink(missing_ok=True)

        perfis = [conta.id_perfil for conta in contas]
        self.assertEqual(len(perfis), 3)
        self.assertEqual(len(perfis), len(set(perfis)))
        self.assertTrue(all(perfil for perfil in perfis))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
