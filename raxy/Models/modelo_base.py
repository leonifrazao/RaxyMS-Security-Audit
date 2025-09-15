"""Classe base para modelos persistiveis com SQLAlchemy."""

from __future__ import annotations

from typing import Any, ClassVar, Dict, Mapping

from sqlalchemy.orm import DeclarativeBase


class BaseDeclarativa(DeclarativeBase):
    """Base declarativa compartilhada entre os modelos."""


class ModeloBase(BaseDeclarativa):
    """Modelo base com suporte a chaves compostas e utilitarios.

    Subclasses devem definir ``CHAVES`` como uma tupla de campos que
    identificam unicamente uma instancia (ex.: ``("email",)`` ou
    ``("email", "id_perfil")``).
    """

    __abstract__ = True

    CHAVES: ClassVar[tuple[str, ...]] = ()

    def to_dict(self) -> Dict[str, Any]:
        """Converte o modelo para ``dict`` usando as colunas mapeadas."""

        return {col.key: getattr(self, col.key) for col in self.__mapper__.columns}

    def chaves_definidas(self) -> Dict[str, Any]:
        """Retorna o subconjunto de chaves com valores nao nulos."""

        if not self.CHAVES:
            raise ValueError(f"Modelo {type(self).__name__} nao definiu CHAVES")
        chaves: Dict[str, Any] = {}
        for chave in self.CHAVES:
            if not hasattr(self, chave):
                raise AttributeError(f"Campo chave '{chave}' inexistente em {type(self).__name__}")
            valor = getattr(self, chave)
            if valor is not None:
                chaves[chave] = valor
        return chaves

    @classmethod
    def validar_definicao(cls) -> None:
        """Garante que a classe declare ao menos uma chave."""

        if not cls.CHAVES:
            raise ValueError(f"Modelo {cls.__name__} deve declarar ao menos uma chave em CHAVES")
