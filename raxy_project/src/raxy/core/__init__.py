"""
Raxy Core Module - Compatibility Layer

This module provides backward compatibility for imports from the old structure.
All components have been moved to:
- raxy.core.domain -> Domain entities
- raxy.core.services -> Business services
- raxy.core.exceptions -> Exception hierarchy
"""

# Re-export from new locations
from raxy.core.domain import (
    Conta,
    Proxy,
    SessionState,
    EtapaResult,
    ContaResult,
)

from raxy.core.exceptions import *

__all__ = [
    "Conta",
    "Proxy", 
    "SessionState",
    "EtapaResult",
    "ContaResult",
]
