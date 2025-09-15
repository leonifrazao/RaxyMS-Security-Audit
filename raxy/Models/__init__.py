"""Modelos estruturados para serem persistidos via handlers de dados."""

from .modelo_base import ModeloBase, BaseDeclarativa
from .conta_modelo import ModeloConta

__all__ = ["ModeloBase", "BaseDeclarativa", "ModeloConta"]
