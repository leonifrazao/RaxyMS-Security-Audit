"""
Entidades de Proxy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Proxy:
    """Representa um servidor Proxy (Imutável)."""
    
    id: str
    url: str
    type: str = "http"
    country: Optional[str] = None
    city: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        return bool(self.url)

    @property
    def protocol(self) -> str:
        """Retorna o protocolo normalizado."""
        return self.type.lower()
