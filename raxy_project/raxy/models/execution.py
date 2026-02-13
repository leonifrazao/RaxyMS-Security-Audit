from dataclasses import dataclass, field
from typing import List, Any, Optional
from .accounts import Conta

# Re-exporting ContaResult from executor_service if it moves here or defining a new one if it remains there.
# Since ContaResult is currently in executor_service, I should probably check if I should move it here too.
# The user request mentioned "use domain no return", implying moving DTOs to domain.
# Let's verify where ContaResult is defined. It was in executor_service.py.
# I will define BatchExecutionResult here and import other necessary types.

# Forward declaration for type hinting if needed, but for now using Any for simplicity to avoid circular imports if ContaResult stays in service.
# Ideally ContaResult should also be a domain object.
# Let's check executor_service.py content again effectively.
# It has ContaResult. I should move ContaResult to this file as well for better domain cohesion.

@dataclass
class EtapaResult:
    """Result of a single execution step."""
    nome: str
    sucesso: bool
    erro: Optional[str] = None
    dados: Optional[dict[str, Any]] = None

@dataclass
class ContaResult:
    """Detailed result of processing a single account."""
    email: str
    sucesso_geral: bool
    pontos_iniciais: int = 0
    pontos_finais: int = 0
    pontos_ganhos: int = 0
    etapas: List[EtapaResult] = field(default_factory=list)
    erro_fatal: Optional[str] = None
    proxy_usado: Optional[str] = None

    def adicionar_etapa(self, nome: str, sucesso: bool, erro: Optional[str] = None, dados: Optional[dict[str, Any]] = None) -> None:
        self.etapas.append(EtapaResult(nome, sucesso, erro, dados))

@dataclass(frozen=True)
class BatchExecutionResult:
    """Represents the overall result of a batch execution."""
    total_contas: int
    contas_sucesso: int
    contas_falha: int
    pontos_totais: int
    resultados_detalhados: List[ContaResult]
