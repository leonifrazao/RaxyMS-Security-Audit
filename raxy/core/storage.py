"""Camada de armazenamento utilizando SQLAlchemy."""

from __future__ import annotations

from pathlib import Path
import threading
from types import MethodType
from typing import Callable, Mapping, Type, TypeVar

try:
    from sqlalchemy import and_, create_engine, delete, select, inspect
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session, sessionmaker
except ModuleNotFoundError as exc:  # pragma: no cover - depende do ambiente
    raise ModuleNotFoundError(
        "SQLAlchemy nao encontrado. Instale com 'pip install sqlalchemy'."
    ) from exc

from raxy.Models.modelo_base import ModeloBase, BaseDeclarativa

ModeloT = TypeVar("ModeloT", bound=ModeloBase)


_ENGINE_CACHE: dict[tuple[str, bool], Engine] = {}
_SESSION_FACTORY_CACHE: dict[tuple[str, bool], sessionmaker] = {}
_METADATA_INICIALIZADA: set[tuple[str, bool]] = set()
_CACHE_LOCK = threading.RLock()


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
        """Instancia a base de modelos e prepara a conexão com o banco.

        Args:
            url_banco: URL SQLAlchemy. Quando ``None``, cria ``dados.db`` (SQLite).
            echo_sql: Ativa o log de instruções SQL para depuração.
            metodos_personalizados: Mapeamento ``nome -> função`` a ser ligado na
                instância para estender o comportamento padrão.
        """

        if url_banco is None:
            arquivo_db = Path("dados.db").resolve()
            arquivo_db.parent.mkdir(parents=True, exist_ok=True)
            url_banco = f"sqlite:///{arquivo_db}"

        cache_key = (url_banco, bool(echo_sql))
        with _CACHE_LOCK:
            engine = _ENGINE_CACHE.get(cache_key)
            if engine is None:
                engine = create_engine(url_banco, echo=echo_sql, future=True)
                _ENGINE_CACHE[cache_key] = engine
            if cache_key not in _METADATA_INICIALIZADA:
                BaseDeclarativa.metadata.create_all(engine)
                _METADATA_INICIALIZADA.add(cache_key)

            session_factory = _SESSION_FACTORY_CACHE.get(cache_key)
            if session_factory is None:
                session_factory = sessionmaker(
                    bind=engine,
                    autoflush=False,
                    future=True,
                    expire_on_commit=False,
                )
                _SESSION_FACTORY_CACHE[cache_key] = session_factory

        self._engine = engine
        self._session_factory = session_factory

        if metodos_personalizados:
            for nome, funcao in metodos_personalizados.items():
                if not callable(funcao):
                    raise TypeError(f"Metodo personalizado '{nome}' nao e chamavel")
                setattr(self, nome, MethodType(funcao, self))

    # ------------------------------------------------------------------
    # Operacoes CRUD basicas
    # ------------------------------------------------------------------

    def obter(self, classe_modelo: Type[ModeloT]) -> list[ModeloT]:
        """Retorna todos os registros do modelo informado.

        Args:
            classe_modelo: Classe derivada de :class:`ModeloBase`.

        Returns:
            Lista contendo todas as instâncias persistidas.
        """

        classe_modelo.validar_definicao()
        with self._session_factory() as sessao:
            return list(sessao.scalars(select(classe_modelo)))

    def obter_por_id(self, identificador: int, classe_modelo: Type[ModeloT]) -> ModeloT | None:
        """Busca um registro pelo valor exato do ID primário.

        Args:
            identificador: Valor da chave primária.
            classe_modelo: Classe do modelo.

        Returns:
            Instância correspondente ou ``None`` se inexistente.
        """

        info = inspect(classe_modelo)
        pk_cols = info.primary_key
        if not pk_cols:
            raise ValueError(
                f"Modelo {classe_modelo.__name__} nao possui chave primaria definida"
            )
        if len(pk_cols) != 1:
            raise ValueError(
                "Consultas por ID exigem chave primaria simples"
            )
        with self._session_factory() as sessao:
            return sessao.get(classe_modelo, identificador)

    def obter_por_key(self, modelo: ModeloT) -> list[ModeloT]:
        """Busca registros que combinem com as chaves preenchidas no ``modelo``.

        Args:
            modelo: Instância parcialmente preenchida indicando as chaves.

        Returns:
            Lista de registros compatíveis.
        """

        filtros = modelo.chaves_definidas()
        if not filtros:
            raise ValueError("Informe ao menos uma chave do modelo para executar a operacao")
        classe_modelo = type(modelo)
        condicoes = [getattr(classe_modelo, chave) == valor for chave, valor in filtros.items()]
        if not condicoes:
            raise ValueError("Pelo menos uma condicao e necessaria")
        condicao = condicoes[0] if len(condicoes) == 1 else and_(*condicoes)
        consulta = select(classe_modelo).where(condicao)
        with self._session_factory() as sessao:
            return list(sessao.scalars(consulta))

    def inserir_ou_atualizar(self, modelo: ModeloT) -> ModeloT:
        """Insere o modelo ou atualiza o registro existente com as mesmas chaves.

        Args:
            modelo: Instância do modelo com dados a persistir.

        Returns:
            Instância persistida (nova ou atualizada).
        """

        filtros = modelo.chaves_definidas()
        if not filtros:
            raise ValueError("Informe ao menos uma chave do modelo para executar a operacao")
        classe_modelo = type(modelo)
        condicoes = [getattr(classe_modelo, chave) == valor for chave, valor in filtros.items()]
        if not condicoes:
            raise ValueError("Pelo menos uma condicao e necessaria")
        condicao = condicoes[0] if len(condicoes) == 1 else and_(*condicoes)

        with self._session_factory() as sessao:
            existente = sessao.scalars(select(classe_modelo).where(condicao)).first()
            if existente:
                dados = modelo.to_dict()
                info = inspect(classe_modelo)
                pk_cols = info.primary_key
                if not pk_cols:
                    raise ValueError(
                        f"Modelo {classe_modelo.__name__} nao possui chave primaria definida"
                    )
                if len(pk_cols) != 1:
                    raise ValueError("Atualizacoes exigem chave primaria simples")
                pk_nome = pk_cols[0].key
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
        """Remove registros que coincidam com as chaves preenchidas.

        Args:
            modelo: Instância contendo as chaves usadas como filtro.

        Returns:
            Número de registros afetados.
        """

        filtros = modelo.chaves_definidas()
        if not filtros:
            raise ValueError("Informe ao menos uma chave do modelo para executar a operacao")
        classe_modelo = type(modelo)
        condicoes = [getattr(classe_modelo, chave) == valor for chave, valor in filtros.items()]
        if not condicoes:
            raise ValueError("Pelo menos uma condicao e necessaria")
        condicao = condicoes[0] if len(condicoes) == 1 else and_(*condicoes)

        with self._session_factory() as sessao:
            resultado = sessao.execute(delete(classe_modelo).where(condicao))
            sessao.commit()
            return resultado.rowcount or 0

    def remover_por_key(
        self,
        modelo: ModeloT,
        predicado: Callable[[ModeloT], bool] | None = None,
    ) -> int:
        """Remove registros por chave e, opcionalmente, por predicado extra.

        Args:
            modelo: Instância indicando as chaves a considerar.
            predicado: Função adicional para filtrar instâncias antes da remoção.

        Returns:
            Número de registros efetivamente removidos.
        """

        if predicado is not None and not callable(predicado):
            raise TypeError("Predicado precisa ser uma funcao ou None")

        filtros = modelo.chaves_definidas()
        if not filtros:
            raise ValueError("Informe ao menos uma chave do modelo para executar a operacao")
        classe_modelo = type(modelo)
        condicoes = [getattr(classe_modelo, chave) == valor for chave, valor in filtros.items()]
        if not condicoes:
            raise ValueError("Pelo menos uma condicao e necessaria")
        condicao = condicoes[0] if len(condicoes) == 1 else and_(*condicoes)

        with self._session_factory() as sessao:
            if predicado is None:
                resultado = sessao.execute(delete(classe_modelo).where(condicao))
                sessao.commit()
                return resultado.rowcount or 0

            consulta = select(classe_modelo).where(condicao)
            removidos = 0
            for registro in sessao.scalars(consulta):
                if predicado(registro):
                    sessao.delete(registro)
                    removidos += 1
            sessao.commit()
            return removidos

    def atualizar_por_id(self, identificador: int, modelo: ModeloT) -> ModeloT | None:
        """Atualiza os dados do registro identificado pelo ID.

        Args:
            identificador: Valor da chave primária.
            modelo: Instância com os novos dados (ID será ignorado).

        Returns:
            Instância atualizada ou ``None`` caso o ID não exista.
        """

        classe_modelo = type(modelo)
        info = inspect(classe_modelo)
        pk_cols = info.primary_key
        if not pk_cols:
            raise ValueError(
                f"Modelo {classe_modelo.__name__} nao possui chave primaria definida"
            )
        if len(pk_cols) != 1:
            raise ValueError("Atualizacoes exigem chave primaria simples")
        chave_id = pk_cols[0].key

        with self._session_factory() as sessao:
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
        """Remove um registro com base em seu ID primário.

        Args:
            identificador: Valor da chave primária.
            classe_modelo: Classe do modelo manipulado.

        Returns:
            ``1`` quando removeu o registro, ``0`` caso contrário.
        """

        info = inspect(classe_modelo)
        pk_cols = info.primary_key
        if not pk_cols:
            raise ValueError(
                f"Modelo {classe_modelo.__name__} nao possui chave primaria definida"
            )
        if len(pk_cols) != 1:
            raise ValueError("Remocao por ID exige chave primaria simples")
        with self._session_factory() as sessao:
            existente = sessao.get(classe_modelo, identificador)
            if not existente:
                return 0
            sessao.delete(existente)
            sessao.commit()
            return 1

__all__ = ["BaseModelos"]
