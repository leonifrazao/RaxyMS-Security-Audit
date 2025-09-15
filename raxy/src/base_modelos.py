"""Camada de armazenamento utilizando SQLAlchemy."""

from __future__ import annotations

from pathlib import Path
from types import MethodType
from typing import Callable, Mapping, Type, TypeVar

try:
    from sqlalchemy import and_, create_engine, delete, select, inspect
    from sqlalchemy.orm import Session, sessionmaker
except ModuleNotFoundError as exc:  # pragma: no cover - depende do ambiente
    raise ModuleNotFoundError(
        "SQLAlchemy nao encontrado. Instale com 'pip install sqlalchemy'."
    ) from exc

from Models.modelo_base import ModeloBase, BaseDeclarativa

ModeloT = TypeVar("ModeloT", bound=ModeloBase)


class BaseModelos:
    """Handler generico para CRUD sobre modelos baseados em ``ModeloBase``.

    Permite opcionalmente registrar metodos personalizados ao instanciar a base
    para comportamentos especificos (ex.: ``aumentar_pontos``).

    Alem de CRUD basico, oferece:
    - ``obter_por_id``/``atualizar_por_id``/``deletar_por_id`` para manipulacao
      direta via chave primaria.
    - ``remover_por_key`` que remove multiplos registros com base nas chaves
      declaradas no modelo, opcionalmente filtrando por um predicado.
    """

    def __init__(
        self,
        url_banco: str | None = None,
        *,
        echo_sql: bool = False,
        metodos_personalizados: Mapping[str, Callable[..., object]] | None = None,
    ) -> None:
        if url_banco is None:
            arquivo_db = Path("dados.db").resolve()
            arquivo_db.parent.mkdir(parents=True, exist_ok=True)
            url_banco = f"sqlite:///{arquivo_db}"

        self._engine = create_engine(url_banco, echo=echo_sql, future=True)
        BaseDeclarativa.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, future=True, expire_on_commit=False)

        if metodos_personalizados:
            for nome, funcao in metodos_personalizados.items():
                if not callable(funcao):
                    raise TypeError(f"Metodo personalizado '{nome}' nao e chamavel")
                setattr(self, nome, MethodType(funcao, self))

    # ------------------------------------------------------------------
    # Operacoes CRUD basicas
    # ------------------------------------------------------------------

    def obter(self, classe_modelo: Type[ModeloT]) -> list[ModeloT]:
        """Retorna todos os registros do modelo informado."""

        classe_modelo.validar_definicao()
        with self._nova_sessao() as sessao:
            return list(sessao.scalars(select(classe_modelo)))

    def obter_por_id(self, identificador: int, classe_modelo: Type[ModeloT]) -> ModeloT | None:
        """Busca um registro pelo valor exato do ID primario."""

        self._obter_nome_id(classe_modelo)
        with self._nova_sessao() as sessao:
            return sessao.get(classe_modelo, identificador)

    def obter_por_key(self, modelo: ModeloT) -> list[ModeloT]:
        """Busca registros que combinem com as chaves preenchidas no ``modelo``."""

        filtros = self._extrair_filtros(modelo)
        classe_modelo = type(modelo)
        consulta = select(classe_modelo).where(self._montar_condicao(classe_modelo, filtros))
        with self._nova_sessao() as sessao:
            return list(sessao.scalars(consulta))

    def inserir_ou_atualizar(self, modelo: ModeloT) -> ModeloT:
        """Insere o modelo ou atualiza o registro existente com as mesmas chaves."""

        filtros = self._extrair_filtros(modelo)
        classe_modelo = type(modelo)
        condicao = self._montar_condicao(classe_modelo, filtros)

        with self._nova_sessao() as sessao:
            existente = sessao.scalars(select(classe_modelo).where(condicao)).first()
            if existente:
                dados = modelo.to_dict()
                pk_nome = self._obter_nome_id(classe_modelo)
                dados.pop(pk_nome, None)
                for campo, valor in dados.items():
                    setattr(existente, campo, valor)
                sessao.commit()
                sessao.refresh(existente)
                return existente

            sessao.add(modelo)
            sessao.commit()
            sessao.refresh(modelo)
            return modelo

    def delete(self, modelo: ModeloT) -> int:
        """Remove registros que coincidam com as chaves preenchidas."""

        filtros = self._extrair_filtros(modelo)
        classe_modelo = type(modelo)
        condicao = self._montar_condicao(classe_modelo, filtros)

        with self._nova_sessao() as sessao:
            resultado = sessao.execute(delete(classe_modelo).where(condicao))
            sessao.commit()
            return resultado.rowcount or 0

    def remover_por_key(
        self,
        modelo: ModeloT,
        predicado: Callable[[ModeloT], bool] | None = None,
    ) -> int:
        """Remove varios registros que atendam as chaves (e opcionalmente um predicado)."""

        if predicado is not None and not callable(predicado):
            raise TypeError("Predicado precisa ser uma funcao ou None")

        filtros = self._extrair_filtros(modelo)
        classe_modelo = type(modelo)
        condicao = self._montar_condicao(classe_modelo, filtros)

        with self._nova_sessao() as sessao:
            consulta = select(classe_modelo).where(condicao)
            registros = list(sessao.scalars(consulta))
            if predicado is not None:
                registros = [item for item in registros if predicado(item)]

            removidos = 0
            for registro in registros:
                sessao.delete(registro)
                removidos += 1
            sessao.commit()
            return removidos

    def atualizar_por_id(self, identificador: int, modelo: ModeloT) -> ModeloT | None:
        """Atualiza os dados do registro identificado pelo ID."""

        classe_modelo = type(modelo)
        chave_id = self._obter_nome_id(classe_modelo)

        with self._nova_sessao() as sessao:
            existente = sessao.get(classe_modelo, identificador)
            if not existente:
                return None

            dados = modelo.to_dict()
            dados.pop(chave_id, None)

            for campo, valor in dados.items():
                setattr(existente, campo, valor)
            sessao.commit()
            sessao.refresh(existente)
            return existente

    def deletar_por_id(self, identificador: int, classe_modelo: Type[ModeloT]) -> int:
        """Remove um registro com base em seu ID primario."""

        self._obter_nome_id(classe_modelo)
        with self._nova_sessao() as sessao:
            existente = sessao.get(classe_modelo, identificador)
            if not existente:
                return 0
            sessao.delete(existente)
            sessao.commit()
            return 1

    # ------------------------------------------------------------------
    # Utilitarios internos
    # ------------------------------------------------------------------

    def _nova_sessao(self) -> Session:
        return self._session_factory()

    def _extrair_filtros(self, modelo: ModeloT) -> Mapping[str, object]:
        filtros = modelo.chaves_definidas()
        if not filtros:
            raise ValueError("Informe ao menos uma chave do modelo para executar a operacao")
        return filtros

    def _montar_condicao(
        self,
        classe_modelo: Type[ModeloT],
        filtros: Mapping[str, object],
    ):
        condicoes = [getattr(classe_modelo, chave) == valor for chave, valor in filtros.items()]
        if not condicoes:
            raise ValueError("Pelo menos uma condicao e necessaria")
        if len(condicoes) == 1:
            return condicoes[0]
        return and_(*condicoes)

    def _obter_nome_id(self, classe_modelo: Type[ModeloT]) -> str:
        info = inspect(classe_modelo)
        pk_cols = info.primary_key
        if not pk_cols:
            raise ValueError(f"Modelo {classe_modelo.__name__} nao possui chave primaria definida")
        if len(pk_cols) != 1:
            raise ValueError(
                f"Operacoes por ID exigem chave primaria simples; encontrado {len(pk_cols)} colunas"
            )
        return pk_cols[0].key


__all__ = ["BaseModelos"]
