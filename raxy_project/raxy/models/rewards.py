"""Entidades relacionadas ao Microsoft Rewards."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict


@dataclass
class Promotion:
    """Representa uma promoção ou tarefa do Rewards."""
    id: str
    title: str
    points: int
    complete: bool
    type: Optional[str] = None
    hash: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    date: Optional[str] = None
    
    point_progress: int = 0
    point_progress_max: int = 0
    
    # Metadata adicional que pode vir da API
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PunchCard:
    """Representa um cartão de perfuração (Punch Card)."""
    name: str
    parent_promotion: Optional[Promotion] = None
    child_promotions: List[Promotion] = field(default_factory=list)
    
    @property
    def total_points(self) -> int:
        """Pontos totais do punch card (geralmente no pai)."""
        return self.parent_promotion.points if self.parent_promotion else 0
    
    @property
    def is_complete(self) -> bool:
        """Verifica se o punch card está completo."""
        parent_complete = self.parent_promotion.complete if self.parent_promotion else False
        children_complete = all(p.complete for p in self.child_promotions)
        return parent_complete or children_complete # Simplification logic, varies


@dataclass
class DailySet:
    """Representa um conjunto diário de tarefas."""
    date: str
    promotions: List[Promotion] = field(default_factory=list)
    
    @property
    def is_complete(self) -> bool:
        """Verifica se todo o set está completo."""
        return all(p.complete for p in self.promotions)
    
    @property
    def total_points(self) -> int:
        """Total de pontos do set."""
        return sum(p.points for p in self.promotions if p.points)


@dataclass
class RewardsDashboard:
    """Representa o painel do Rewards com tarefas disponíveis."""
    daily_sets: List[DailySet] = field(default_factory=list)
    more_promotions: List[Promotion] = field(default_factory=list)
    punch_cards: List[PunchCard] = field(default_factory=list)
    promotional_items: List[Promotion] = field(default_factory=list)
    user_status: Dict[str, Any] = field(default_factory=dict)
    
    # Dados brutos para debug/uso futuro se necessário
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def all_promotions(self) -> List[Promotion]:
        """Retorna todas as promoções em uma única lista."""
        promos = []
        for clay in self.daily_sets:
            promos.extend(clay.promotions)
        promos.extend(self.more_promotions)
        promos.extend(self.promotional_items)
        for pc in self.punch_cards:
            if pc.parent_promotion:
                promos.append(pc.parent_promotion)
            promos.extend(pc.child_promotions)

        return promos


@dataclass
class TaskResult:
    """Resultado da execução de uma tarefa."""
    promotion_id: str
    success: bool
    points_earned: int = 0
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class CollectionResult:
    """Resultado da coleta de recompensas."""
    tasks_results: List[TaskResult] = field(default_factory=list)
    total_points_earned: int = 0
    tasks_completed_count: int = 0
    tasks_failed_count: int = 0
    
    def add_result(self, result: TaskResult) -> None:
        """Adiciona um resultado de tarefa."""
        self.tasks_results.append(result)
        if result.success:
            self.tasks_completed_count += 1
            self.total_points_earned += result.points_earned
        else:
            self.tasks_failed_count += 1
