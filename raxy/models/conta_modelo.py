"""Modelo de conta utilizando SQLAlchemy."""

from __future__ import annotations

from typing import ClassVar, Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .modelo_base import ModeloBase


class ModeloConta(ModeloBase):
    """Representa uma conta com chave primaria baseada no email."""

    __tablename__ = "contas"

    CHAVES: ClassVar[tuple[str, ...]] = ("email",)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    senha: Mapped[str] = mapped_column(String(255), nullable=False)
    id_perfil: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pontos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
