"""
Entidades de Resultado de Execução.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ContaResult:
    """Resultado processamento de uma conta."""
    
    email: str
    sucesso_geral: bool = False
    pontos_iniciais: int = 0
    pontos_finais: int = 0
    pontos_ganhos: int = 0
    etapas: Dict[str, Any] = field(default_factory=dict)
    erro_fatal: Optional[str] = None
    proxy_usado: Optional[str] = None
    
    def adicionar_etapa(self, nome: str, sucesso: bool, dados: Any = None, erro: str = None):
        self.etapas[nome] = {
            "sucesso": sucesso,
            "dados": dados,
            "erro": erro
        }


@dataclass
class ExecucaoResult:
    """Resultado de uma execução em lote."""
    
    total_contas: int = 0
    sucessos: int = 0
    falhas: int = 0
    total_pontos: int = 0
    detalhes: List[ContaResult] = field(default_factory=list)
