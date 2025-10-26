"""
Event-Driven Logging System.

Sistema completo de logging descentralizado via Event Bus incluindo:
- Eventos estruturados (LogEvent)
- Agregador centralizado (LogAggregator)
- Destinos múltiplos (console, arquivo, JSON)
"""

from __future__ import annotations

import sys
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
from uuid import uuid4

from raxy.interfaces.services import IEventBus, ILoggingService


# ============================================================================
# LOG EVENT
# ============================================================================

@dataclass
class LogEvent:
    """Evento estruturado para logging via Event Bus."""
    
    correlation_id: str = field(default_factory=lambda: str(uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    level: int = 20
    level_name: str = "INFO"
    message: str = ""
    service: str = "raxy"
    context: Dict[str, Any] = field(default_factory=dict)
    location: Dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    exception: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LogEvent:
        """Cria evento a partir de dicionário."""
        return cls(**data)


def create_log_event(
    level: int,
    level_name: str,
    message: str,
    context: Dict[str, Any],
    service: str = "raxy",
    correlation_id: Optional[str] = None,
    exception: Optional[Exception] = None
) -> LogEvent:
    """Factory para criar eventos de log."""
    # Extrai localização
    location = {}
    for key in ['file', 'path', 'line', 'function', 'class', 'module']:
        if key in context:
            location[key] = context.pop(key, None)
    
    # Extrai IDs
    trace_id = context.pop('trace_id', None)
    span_id = context.pop('span_id', None)
    
    if not correlation_id:
        correlation_id = context.get('correlation_id', str(uuid4())[:8])
    
    # Processa exceção
    exception_data = None
    if exception:
        import traceback
        exception_data = {
            'type': exception.__class__.__name__,
            'message': str(exception),
            'traceback': traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        }
    
    # Extrai tags
    tags = context.pop('tags', [])
    if isinstance(tags, str):
        tags = [tags]
    
    return LogEvent(
        correlation_id=correlation_id,
        timestamp=datetime.now().isoformat(),
        level=level,
        level_name=level_name,
        message=message,
        service=service,
        context=context,
        location=location,
        tags=tags,
        trace_id=trace_id,
        span_id=span_id,
        exception=exception_data
    )


# ============================================================================
# LOG AGGREGATOR
# ============================================================================

class LogAggregator:
    """Agregador centralizado de logs via Event Bus."""
    
    def __init__(
        self,
        event_bus: IEventBus,
        logger: Optional[ILoggingService] = None,
        enable_console: bool = True,
        enable_file: bool = False,
        log_file: Optional[str] = None,
        min_level: int = 20
    ):
        self.event_bus = event_bus
        self.min_level = min_level
        
        if logger:
            self._logger = logger
        else:
            from raxy.core.logging import get_logger
            self._logger = get_logger()
        
        self.destinations: List[LogDestination] = []
        
        if enable_console:
            self.add_destination(ConsoleLogDestination(min_level=min_level))
        
        if enable_file and log_file:
            self.add_destination(FileLogDestination(log_file, min_level=min_level))
        
        self.filters: List[Callable[[Dict[str, Any]], bool]] = []
        self.enrichers: List[Callable[[Dict[str, Any]], Dict[str, Any]]] = []
        
        self._metrics = {
            'events_received': 0,
            'events_processed': 0,
            'events_filtered': 0,
            'events_failed': 0
        }
        
        self._register_handler()
    
    def _register_handler(self) -> None:
        """Registra handler no Event Bus."""
        try:
            self.event_bus.subscribe("log.event", self._handle_log_event)
        except Exception as e:
            print(f"Erro ao registrar log aggregator: {e}", file=sys.stderr)
    
    def _handle_log_event(self, data: Dict[str, Any]) -> None:
        """Handler para eventos de log."""
        self._metrics['events_received'] += 1
        
        try:
            level = data.get('level', 20)
            if level < self.min_level:
                self._metrics['events_filtered'] += 1
                return
            
            if not self._apply_filters(data):
                self._metrics['events_filtered'] += 1
                return
            
            enriched_data = self._enrich_event(data)
            self._route_to_destinations(enriched_data)
            
            self._metrics['events_processed'] += 1
            
        except Exception as e:
            self._metrics['events_failed'] += 1
            print(f"Erro ao processar log event: {e}", file=sys.stderr)
    
    def _apply_filters(self, data: Dict[str, Any]) -> bool:
        """Aplica filtros."""
        for filter_func in self.filters:
            try:
                if not filter_func(data):
                    return False
            except Exception as e:
                print(f"Erro no filtro de log: {e}", file=sys.stderr)
        return True
    
    def _enrich_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enriquece evento."""
        enriched = data.copy()
        for enricher in self.enrichers:
            try:
                enriched = enricher(enriched)
            except Exception as e:
                print(f"Erro no enricher: {e}", file=sys.stderr)
        return enriched
    
    def _route_to_destinations(self, data: Dict[str, Any]) -> None:
        """Roteia para destinos."""
        for destination in self.destinations:
            try:
                destination.send(data)
            except Exception as e:
                print(f"Erro ao enviar para destino: {e}", file=sys.stderr)
    
    def add_destination(self, destination: LogDestination) -> None:
        """Adiciona destino."""
        self.destinations.append(destination)
    
    def add_filter(self, filter_func: Callable[[Dict[str, Any]], bool]) -> None:
        """Adiciona filtro."""
        self.filters.append(filter_func)
    
    def add_enricher(self, enricher_func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Adiciona enricher."""
        self.enrichers.append(enricher_func)
    
    def get_metrics(self) -> Dict[str, int]:
        """Retorna métricas."""
        return self._metrics.copy()
    
    def close(self) -> None:
        """Fecha o agregador."""
        for destination in self.destinations:
            try:
                destination.close()
            except Exception:
                pass


# ============================================================================
# LOG DESTINATIONS
# ============================================================================

class LogDestination:
    """Interface para destinos de log."""
    
    def send(self, data: Dict[str, Any]) -> None:
        """Envia log para destino."""
        raise NotImplementedError
    
    def close(self) -> None:
        """Fecha destino."""
        pass


class ConsoleLogDestination(LogDestination):
    """Destino: console."""
    
    def __init__(self, min_level: int = 20, use_colors: bool = True):
        self.min_level = min_level
        from raxy.core.logging.formatters import ConsoleFormatter
        self.formatter = ConsoleFormatter(
            use_colors=use_colors,
            show_time=True,
            show_location=True,
            compact=False
        )
    
    def send(self, data: Dict[str, Any]) -> None:
        """Envia para console."""
        level = data.get('level', 20)
        if level < self.min_level:
            return
        
        try:
            formatted = self.formatter.format(
                level=level,
                message=data.get('message', ''),
                timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat())),
                context={
                    **data.get('context', {}),
                    **data.get('location', {})
                },
                exception=None
            )
            print(formatted)
        except Exception as e:
            print(f"Erro ao formatar log: {e}", file=sys.stderr)


class FileLogDestination(LogDestination):
    """Destino: arquivo."""
    
    def __init__(
        self,
        filename: str | Path,
        min_level: int = 20,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5
    ):
        self.filename = Path(filename)
        self.min_level = min_level
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.filename, 'a', encoding='utf-8')
        
        from raxy.core.logging.formatters import FileFormatter
        self.formatter = FileFormatter(include_context=True)
    
    def send(self, data: Dict[str, Any]) -> None:
        """Envia para arquivo."""
        level = data.get('level', 20)
        if level < self.min_level:
            return
        
        try:
            self._check_rotation()
            
            formatted = self.formatter.format(
                level=level,
                message=data.get('message', ''),
                timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat())),
                context={
                    **data.get('context', {}),
                    **data.get('location', {})
                },
                exception=None
            )
            
            self._file.write(formatted + '\n')
            self._file.flush()
        except Exception as e:
            print(f"Erro ao escrever em arquivo: {e}", file=sys.stderr)
    
    def _check_rotation(self) -> None:
        """Verifica rotação."""
        try:
            if self.max_bytes > 0 and self.filename.stat().st_size >= self.max_bytes:
                self._rotate()
        except Exception:
            pass
    
    def _rotate(self) -> None:
        """Rotaciona arquivo."""
        try:
            self._file.close()
            
            for i in range(self.backup_count - 1, 0, -1):
                old_name = Path(f"{self.filename}.{i}")
                new_name = Path(f"{self.filename}.{i+1}")
                
                if old_name.exists():
                    if new_name.exists():
                        new_name.unlink()
                    old_name.rename(new_name)
            
            backup_name = Path(f"{self.filename}.1")
            if backup_name.exists():
                backup_name.unlink()
            if self.filename.exists():
                self.filename.rename(backup_name)
            
            self._file = open(self.filename, 'a', encoding='utf-8')
        except Exception as e:
            print(f"Erro ao rotacionar: {e}", file=sys.stderr)
    
    def close(self) -> None:
        """Fecha arquivo."""
        if self._file:
            self._file.close()


class JSONLogDestination(LogDestination):
    """Destino: JSON."""
    
    def __init__(self, filename: str | Path, min_level: int = 20):
        self.filename = Path(filename)
        self.min_level = min_level
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.filename, 'a', encoding='utf-8')
    
    def send(self, data: Dict[str, Any]) -> None:
        """Envia em JSON."""
        level = data.get('level', 20)
        if level < self.min_level:
            return
        
        try:
            json_line = json.dumps(data, ensure_ascii=False, default=str)
            self._file.write(json_line + '\n')
            self._file.flush()
        except Exception as e:
            print(f"Erro ao escrever JSON: {e}", file=sys.stderr)
    
    def close(self) -> None:
        """Fecha arquivo."""
        if self._file:
            self._file.close()
