"""Contrato para serviços que controlam o navegador do Rewards."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from raxy.services.session_service import BaseRequest


class IRewardsBrowserService(ABC):
    """Define as operações que interagem com o navegador do Rewards."""

    @abstractmethod
    def open_rewards_page(self, *, profile: str, data: Mapping[str, object] | None = None) -> None:
        """Abre a página de Rewards utilizando o perfil informado."""

    @abstractmethod
    def login(self, *, profile: str, data: Mapping[str, object] | None = None) -> "BaseRequest":
        """Realiza o login e devolve uma base de requests autenticada."""
