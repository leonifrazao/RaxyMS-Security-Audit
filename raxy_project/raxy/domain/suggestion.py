from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass
class Suggestion:
    """Representa uma sugestão de busca."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
