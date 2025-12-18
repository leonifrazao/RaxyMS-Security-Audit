"""Entidades de Resultado de Execução."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class EtapaResult:
    """Resultado de uma etapa individual."""
    nome: str
    sucesso: bool
    erro: Optional[str] = None
    dados: Optional[Dict[str, Any]] = None


@dataclass
class ContaResult:
    """Resultado detalhado do processamento de uma conta."""
    email: str
    sucesso_geral: bool
    pontos_iniciais: int = 0
    pontos_finais: int = 0
    pontos_ganhos: int = 0
    etapas: List[EtapaResult] = field(default_factory=list)
    erro_fatal: Optional[str] = None
    proxy_usado: Optional[str] = None
    
    def adicionar_etapa(self, nome: str, sucesso: bool, erro: Optional[str] = None, dados: Optional[Dict[str, Any]] = None) -> None:
        """Adiciona resultado de uma etapa."""
        self.etapas.append(EtapaResult(
            nome=nome,
            sucesso=sucesso,
            erro=erro,
            dados=dados
        ))
    
    def get_resumo(self) -> Dict[str, Any]:
        """Retorna resumo do resultado."""
        etapas_ok = sum(1 for e in self.etapas if e.sucesso)
        etapas_falha = len(self.etapas) - etapas_ok
        
        return {
            "email": self.email,
            "sucesso": self.sucesso_geral,
            "pontos_iniciais": self.pontos_iniciais,
            "pontos_finais": self.pontos_finais,
            "pontos_ganhos": self.pontos_ganhos,
            "etapas_ok": etapas_ok,
            "etapas_falha": etapas_falha,
            "total_etapas": len(self.etapas),
            "erro_fatal": self.erro_fatal,
            "proxy": self.proxy_usado,
            "detalhes_etapas": [
                {
                    "nome": e.nome,
                    "sucesso": e.sucesso,
                    "erro": e.erro
                }
                for e in self.etapas
            ]
        }
