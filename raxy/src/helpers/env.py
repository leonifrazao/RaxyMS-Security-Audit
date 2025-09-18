"""Funcoes auxiliares para ler variaveis de ambiente de forma consistente."""

from __future__ import annotations

import os
from typing import Callable, Iterable, Optional, TypeVar

_T = TypeVar("_T")

_TRUTHY = {"1", "true", "sim", "yes", "on"}
_FALSY = {"0", "false", "nao", "no", "off"}


def get_env_bool(nome: str, padrao: Optional[bool] = None) -> Optional[bool]:
    """Interpreta a variavel ``nome`` como booleana caso exista."""

    valor = os.getenv(nome)
    if valor is None:
        return padrao
    normalizado = valor.strip().lower()
    if not normalizado:
        return padrao
    if normalizado in _TRUTHY:
        return True
    if normalizado in _FALSY:
        return False
    return padrao


def get_env_int(nome: str, padrao: Optional[int] = None) -> Optional[int]:
    """Interpreta a variavel ``nome`` como inteiro, retornando ``padrao`` em erro."""

    valor = os.getenv(nome)
    if valor is None:
        return padrao
    try:
        return int(valor.strip())
    except (TypeError, ValueError):
        return padrao


def get_env_list(
    nome: str,
    *,
    padrao: Optional[Iterable[str]] = None,
    separador: str = ",",
    normalizar: Callable[[str], str] | None = str.strip,
) -> list[str]:
    """Converte uma variavel em lista de strings limpando valores vazios."""

    valor = os.getenv(nome)
    if valor is None:
        return list(padrao or [])
    itens = valor.split(separador)
    resultado: list[str] = []
    for item in itens:
        texto = normalizar(item) if normalizar else item
        if texto:
            resultado.append(texto)
    if not resultado and padrao is not None:
        return list(padrao)
    return resultado


def get_env_value(
    nome: str,
    conversor: Callable[[str], _T],
    *,
    padrao: Optional[_T] = None,
) -> Optional[_T]:
    """Retorna o valor convertido pela funcao ``conversor`` com fallback em falhas."""

    valor = os.getenv(nome)
    if valor is None:
        return padrao
    try:
        return conversor(valor)
    except Exception:  # pragma: no cover - defensivo
        return padrao

__all__ = [
    "get_env_bool",
    "get_env_int",
    "get_env_list",
    "get_env_value",
]
