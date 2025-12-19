"""
Mock Database Client para testes unitários.

Implementação em memória que não toca banco de dados real.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Sequence
from copy import deepcopy

from raxy.interfaces.database import IDatabaseClient


class MockDatabaseClient(IDatabaseClient):
    """
    Database mock para testes.
    
    Armazena todos os dados em dicionário Python,
    sem tocar banco real.
    
    Design Pattern: Test Double (Mock Object)
    Uso: Testes unitários
    
    Benefícios:
    - Execução instantânea (<1ms)
    - Zero conexão de rede
    - Determinístico
    - Isolamento perfeito entre testes
    """
    
    def __init__(self):
        """Inicializa database mock."""
        # Estrutura: {table_name: {id: record}}
        self._tables: Dict[str, Dict[int, Dict[str, Any]]] = {}
        self._next_ids: Dict[str, int] = {}
        self._is_healthy = True
    
    def _ensure_table(self, table: str) -> None:
        """Garante que tabela existe."""
        if table not in self._tables:
            self._tables[table] = {}
            self._next_ids[table] = 1
    
    def _get_next_id(self, table: str) -> int:
        """Obtém próximo ID para tabela."""
        next_id = self._next_ids.get(table, 1)
        self._next_ids[table] = next_id + 1
        return next_id
    
    def _matches_filters(self, record: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Verifica se registro corresponde aos filtros."""
        for key, value in filters.items():
            if key not in record or record[key] != value:
                return False
        return True
    
    def upsert(
        self,
        table: str,
        data: Dict[str, Any],
        on_conflict: str
    ) -> Optional[Dict[str, Any]]:
        """Insere ou atualiza registro."""
        self._ensure_table(table)
        
        # Procura registro existente pelo campo de conflito
        conflict_value = data.get(on_conflict)
        existing_id = None
        
        if conflict_value:
            for record_id, record in self._tables[table].items():
                if record.get(on_conflict) == conflict_value:
                    existing_id = record_id
                    break
        
        if existing_id:
            # Atualiza existente
            self._tables[table][existing_id].update(data)
            return deepcopy(self._tables[table][existing_id])
        else:
            # Insere novo
            new_id = self._get_next_id(table)
            record = {"id": new_id, **data}
            self._tables[table][new_id] = record
            return deepcopy(record)
    
    def select(
        self,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> Sequence[Dict[str, Any]]:
        """Seleciona registros."""
        self._ensure_table(table)
        
        results = []
        
        for record in self._tables[table].values():
            if filters is None or self._matches_filters(record, filters):
                # Copia registro
                result = deepcopy(record)
                
                # Filtra colunas se necessário
                if columns != "*":
                    cols = [c.strip() for c in columns.split(",")]
                    result = {k: v for k, v in result.items() if k in cols}
                
                results.append(result)
                
                # Aplica limite
                if limit and len(results) >= limit:
                    break
        
        return results
    
    def select_one(
        self,
        table: str,
        filters: Dict[str, Any],
        columns: str = "*"
    ) -> Optional[Dict[str, Any]]:
        """Seleciona um único registro."""
        results = self.select(table, columns, filters, limit=1)
        return results[0] if results else None
    
    def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Atualiza registros."""
        self._ensure_table(table)
        
        updated = None
        
        for record in self._tables[table].values():
            if self._matches_filters(record, filters):
                record.update(data)
                if updated is None:
                    updated = deepcopy(record)
        
        return updated
    
    def delete(
        self,
        table: str,
        filters: Dict[str, Any]
    ) -> bool:
        """Remove registros."""
        self._ensure_table(table)
        
        ids_to_remove = []
        
        for record_id, record in self._tables[table].items():
            if self._matches_filters(record, filters):
                ids_to_remove.append(record_id)
        
        for record_id in ids_to_remove:
            del self._tables[table][record_id]
        
        return len(ids_to_remove) > 0
    
    def health_check(self) -> bool:
        """Verifica saúde (sempre True para mock)."""
        return self._is_healthy
    
    # ========== Métodos de Teste ==========
    
    def clear(self) -> None:
        """Limpa todos os dados (útil para testes)."""
        self._tables.clear()
        self._next_ids.clear()
    
    def clear_table(self, table: str) -> None:
        """Limpa uma tabela específica."""
        if table in self._tables:
            self._tables[table].clear()
            self._next_ids[table] = 1
    
    def get_all_tables(self) -> Dict[str, Dict[int, Dict[str, Any]]]:
        """Retorna todos os dados (útil para debugging)."""
        return deepcopy(self._tables)
    
    def get_table_count(self, table: str) -> int:
        """Retorna número de registros em tabela."""
        return len(self._tables.get(table, {}))
    
    def set_unhealthy(self) -> None:
        """Simula DB não saudável (para testes)."""
        self._is_healthy = False
    
    def set_healthy(self) -> None:
        """Restaura DB saudável."""
        self._is_healthy = True
