"""
Entidades de Estado da Sessão.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class SessionState:
    """Representa o estado de uma sessão de navegador."""
    
    cookies: Dict[str, str] = field(default_factory=dict)
    user_agent: str = ""
    token_antifalsificacao: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        return bool(self.cookies and self.user_agent)
