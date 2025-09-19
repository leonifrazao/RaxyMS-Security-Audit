"""Testes para a camada de armazenamento de modelos."""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from Models import ModeloConta, ModeloBase  # noqa: E402  pylint: disable=wrong-import-position
    from raxy.core.storage import BaseModelos  # noqa: E402  pylint: disable=wrong-import-position
    from sqlalchemy import Integer, String  # noqa: E402  pylint: disable=wrong-import-position
    from sqlalchemy.orm import Mapped, mapped_column  # noqa: E402  pylint: disable=wrong-import-position

    SQLALCHEMY_DISPONIVEL = True

    class ModeloGrupo(ModeloBase):
        """Modelo auxiliar utilizado nos testes de remoção em massa."""

        __tablename__ = "grupos"
        CHAVES = ("grupo", "categoria")

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        grupo: Mapped[str] = mapped_column(String(100), nullable=False)
        categoria: Mapped[str] = mapped_column(String(100), nullable=False)
        pontos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

except ModuleNotFoundError:
    SQLALCHEMY_DISPONIVEL = False


@unittest.skipUnless(SQLALCHEMY_DISPONIVEL, "SQLAlchemy nao esta disponivel no ambiente de testes")
class TestBaseModelos(unittest.TestCase):
    """Garante o comportamento do handler de modelos com SQLAlchemy."""

    def setUp(self) -> None:
        """Cria uma instância de ``BaseModelos`` com SQLite em memória."""

        self.base = BaseModelos(url_banco="sqlite:///:memory:")

    def test_inserir_e_obter_modelos(self) -> None:
        """Valida inserção e recuperação básica de registros."""

        conta = ModeloConta(email="user@example.com", senha="123")
        self.base.inserir_ou_atualizar(conta)

        encontrados = self.base.obter(ModeloConta)
        self.assertEqual(len(encontrados), 1)
        self.assertEqual(encontrados[0].email, "user@example.com")

    def test_inserir_atualiza_quando_chave_existente(self) -> None:
        """Confere a atualização quando um registro com mesma chave já existe."""

        conta = ModeloConta(email="user@example.com", senha="123", pontos=10)
        self.base.inserir_ou_atualizar(conta)

        atualizada = ModeloConta(email="user@example.com", senha="456", id_perfil="abc", pontos=30)
        resultado = self.base.inserir_ou_atualizar(atualizada)

        self.assertEqual(resultado.senha, "456")
        self.assertEqual(resultado.id_perfil, "abc")
        self.assertEqual(resultado.pontos, 30)

    def test_obter_por_key_com_chave_parcial(self) -> None:
        """Garante que a busca por chave parcial retorna apenas a conta alvo."""

        primeira = ModeloConta(email="alice@example.com", senha="segredo")
        segunda = ModeloConta(email="bruno@example.com", senha="outro")
        self.base.inserir_ou_atualizar(primeira)
        self.base.inserir_ou_atualizar(segunda)

        consulta = ModeloConta(email="alice@example.com", senha="placeholder")
        encontrados = self.base.obter_por_key(consulta)
        self.assertEqual(len(encontrados), 1)
        self.assertEqual(encontrados[0].email, "alice@example.com")

    def test_delete_remove_itens_correspondentes(self) -> None:
        """Certifica que o delete remove apenas o registro correspondente."""

        conta = ModeloConta(email="user@example.com", senha="123")
        outra = ModeloConta(email="outro@example.com", senha="456")
        self.base.inserir_ou_atualizar(conta)
        self.base.inserir_ou_atualizar(outra)

        removidos = self.base.delete(ModeloConta(email="user@example.com", senha="placeholder"))
        self.assertEqual(removidos, 1)
        restantes = self.base.obter(ModeloConta)
        self.assertEqual(len(restantes), 1)
        self.assertEqual(restantes[0].email, "outro@example.com")

    def test_obter_por_id(self) -> None:
        """Valida a recuperação de um registro pelo seu ID."""

        salvo = self.base.inserir_ou_atualizar(ModeloConta(email="user@example.com", senha="123"))
        recuperado = self.base.obter_por_id(salvo.id, ModeloConta)
        self.assertIsNotNone(recuperado)
        self.assertEqual(recuperado.id, salvo.id)

    def test_atualizar_por_id(self) -> None:
        """Garante que atualizar por ID substitui campos corretamente."""

        salvo = self.base.inserir_ou_atualizar(ModeloConta(email="user@example.com", senha="123", pontos=1))
        atualizado = self.base.atualizar_por_id(
            salvo.id,
            ModeloConta(email="user@example.com", senha="xyz", pontos=99),
        )
        self.assertIsNotNone(atualizado)
        self.assertEqual(atualizado.pontos, 99)
        self.assertEqual(atualizado.senha, "xyz")

    def test_deletar_por_id(self) -> None:
        """Verifica a remoção por ID seguida de inexistência."""

        salvo = self.base.inserir_ou_atualizar(ModeloConta(email="user@example.com", senha="123"))
        removidos = self.base.deletar_por_id(salvo.id, ModeloConta)
        self.assertEqual(removidos, 1)
        restante = self.base.obter_por_id(salvo.id, ModeloConta)
        self.assertIsNone(restante)

    def test_operacoes_sem_chave_disparam_erro(self) -> None:
        """Certifica que operações exigem preenchimento de chaves obrigatórias."""

        conta_sem_email = ModeloConta(email=None, senha="123")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            self.base.obter_por_key(conta_sem_email)
        with self.assertRaises(ValueError):
            self.base.inserir_ou_atualizar(conta_sem_email)
        with self.assertRaises(ValueError):
            self.base.delete(conta_sem_email)

    def test_metodo_personalizado(self) -> None:
        """Garante que métodos personalizados são ligados na instância."""

        def aumentar_pontos(handler: BaseModelos, email: str, incremento: int) -> int:
            """Incrementa a pontuação da conta e retorna o novo total."""

            registro = handler.obter_por_key(ModeloConta(email=email, senha="placeholder"))
            if not registro:
                raise ValueError("Conta nao encontrada")
            conta = registro[0]
            conta.pontos += incremento
            handler.inserir_ou_atualizar(conta)
            return conta.pontos

        base = BaseModelos(metodos_personalizados={"aumentar_pontos": aumentar_pontos})
        base.inserir_ou_atualizar(ModeloConta(email="user@example.com", senha="123", pontos=5))

        total = base.aumentar_pontos("user@example.com", 10)
        self.assertEqual(total, 15)

    def test_remover_por_key_sem_predicado(self) -> None:
        """Remove múltiplos registros apenas pelas chaves definidas."""

        self.base.inserir_ou_atualizar(ModeloGrupo(grupo="premium", categoria="bronze", pontos=500))
        self.base.inserir_ou_atualizar(ModeloGrupo(grupo="premium", categoria="ouro", pontos=1500))
        self.base.inserir_ou_atualizar(ModeloGrupo(grupo="basico", categoria="bronze", pontos=100))

        removidos = self.base.remover_por_key(ModeloGrupo(grupo="premium", categoria=None, pontos=0))
        self.assertEqual(removidos, 2)

        restantes = self.base.obter(ModeloGrupo)
        grupos_restantes = sorted((item.grupo, item.categoria) for item in restantes)
        self.assertEqual(grupos_restantes, [("basico", "bronze")])

    def test_remover_por_key_com_predicado(self) -> None:
        """Aplica filtro adicional ao remover registros por key."""

        self.base.inserir_ou_atualizar(ModeloGrupo(grupo="premium", categoria="bronze", pontos=500))
        self.base.inserir_ou_atualizar(ModeloGrupo(grupo="premium", categoria="ouro", pontos=1500))
        self.base.inserir_ou_atualizar(ModeloGrupo(grupo="premium", categoria="diamante", pontos=2500))

        removidos = self.base.remover_por_key(
            ModeloGrupo(grupo="premium", categoria=None, pontos=0),
            predicado=lambda item: item.pontos > 1000,
        )
        self.assertEqual(removidos, 2)

        restantes = self.base.obter(ModeloGrupo)
        pontos_restantes = sorted(item.pontos for item in restantes if item.grupo == "premium")
        self.assertEqual(pontos_restantes, [500])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
