"""
Event Bus Logging Integration.

Sistema completo para logging via Event Bus incluindo:
- EventBusLogHandler: handler assíncrono para publicar logs
- AdaptiveSamplingHandler: handler com sampling adaptativo
- Setup helpers e configuração
"""

from __future__ import annotations

import sys
import queue
import threading
import socket
import os
from typing import Any, Dict, Optional

from raxy.interfaces.services import IEventBus, ILoggingService
from raxy.core.config import LoggerConfig
from raxy.core.logging.handlers import LogHandler
from raxy.core.logging.formatters import ConsoleFormatter
from raxy.core.logging.logger import RaxyLogger


# ============================================================================
# EVENT BUS LOG HANDLER
# ============================================================================

class EventBusLogHandler(LogHandler):
    """Handler que publica logs via Event Bus de forma assíncrona."""
    
    def __init__(
        self,
        event_bus,
        service_name: str = "raxy",
        event_name: str = "log.event",
        formatter: Optional[Any] = None,
        level: int = 0,
        queue_size: int = 10000,
        batch_size: int = 1,
        flush_interval: float = 0.1,
        enable_fallback: bool = True,
        sampling_rate: float = 1.0
    ):
        super().__init__(formatter or ConsoleFormatter(), level)
        
        self.event_bus = event_bus
        self.service_name = service_name
        self.event_name = event_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.enable_fallback = enable_fallback
        self.sampling_rate = max(0.0, min(1.0, sampling_rate))
        
        self.queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        
        self._metrics = {
            'published': 0,
            'dropped': 0,
            'errors': 0,
            'fallback_used': 0
        }
        self._metrics_lock = threading.Lock()
        
        self._fallback_handler = None
        if enable_fallback:
            from raxy.core.logging.handlers import ConsoleHandler
            self._fallback_handler = ConsoleHandler(
                formatter=formatter or ConsoleFormatter(),
                level=level,
                use_stderr=True
            )
        
        self._start_worker()
    
    def _start_worker(self) -> None:
        """Inicia worker thread."""
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="EventBusLogWorker"
        )
        self._worker_thread.start()
    
    def _worker_loop(self) -> None:
        """Loop do worker."""
        batch = []
        
        while not self._stop_event.is_set():
            try:
                try:
                    record = self.queue.get(timeout=self.flush_interval)
                    batch.append(record)
                except queue.Empty:
                    pass
                
                if batch and (len(batch) >= self.batch_size or self._stop_event.is_set()):
                    self._publish_batch(batch)
                    batch.clear()
            except Exception as e:
                print(f"Erro no worker de logs: {e}", file=sys.stderr)
    
    def _publish_batch(self, batch: list) -> None:
        """Publica batch de logs."""
        for record in batch:
            try:
                self._publish_single(record)
            except Exception as e:
                self._handle_publish_error(record, e)
    
    def _publish_single(self, record: Dict[str, Any]) -> None:
        """Publica um log."""
        from raxy.core.events.event_logging import create_log_event
        from raxy.core.config import LEVEL_NAMES
        
        level = record.get('level', 20)
        level_name = LEVEL_NAMES.get(level, 'INFO')
        
        log_event = create_log_event(
            level=level,
            level_name=level_name,
            message=record.get('message', ''),
            context=record.get('context', {}).copy(),
            service=self.service_name,
            correlation_id=record.get('context', {}).get('correlation_id'),
            exception=record.get('exception')
        )
        
        if self.event_bus and hasattr(self.event_bus, 'publish'):
            self.event_bus.publish(self.event_name, log_event.to_dict())
            
            with self._metrics_lock:
                self._metrics['published'] += 1
    
    def _handle_publish_error(self, record: Dict[str, Any], error: Exception) -> None:
        """Trata erro na publicação."""
        with self._metrics_lock:
            self._metrics['errors'] += 1
        
        if self.enable_fallback and self._fallback_handler:
            try:
                self._fallback_handler.emit(record)
                with self._metrics_lock:
                    self._metrics['fallback_used'] += 1
            except Exception:
                print(f"Log fallback failed: {record.get('message', 'N/A')}", file=sys.stderr)
    
    def _should_sample(self) -> bool:
        """Determina se deve amostrar."""
        if self.sampling_rate >= 1.0:
            return True
        import random
        return random.random() < self.sampling_rate
    
    def emit(self, record: Dict[str, Any]) -> None:
        """Adiciona log à queue."""
        if not self._should_sample():
            return
        
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            with self._metrics_lock:
                self._metrics['dropped'] += 1
            
            if self.enable_fallback and self._fallback_handler:
                try:
                    self._fallback_handler.emit(record)
                except Exception:
                    pass
    
    def flush(self) -> None:
        """Força processamento de logs pendentes."""
        try:
            import time
            start_time = time.time()
            timeout = 5.0
            
            while not self.queue.empty():
                if time.time() - start_time > timeout:
                    break
                time.sleep(0.01)
        except Exception:
            pass
    
    def close(self) -> None:
        """Para o handler."""
        self._stop_event.set()
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        
        if self._fallback_handler:
            self._fallback_handler.close()
    
    def get_metrics(self) -> Dict[str, int]:
        """Retorna métricas."""
        with self._metrics_lock:
            return self._metrics.copy()


class AdaptiveSamplingHandler(EventBusLogHandler):
    """Handler com sampling adaptativo baseado em carga."""
    
    def __init__(self, *args, **kwargs):
        kwargs.pop('sampling_rate', None)
        super().__init__(*args, sampling_rate=1.0, **kwargs)
        
        self.min_sampling_rate = 0.1
        self.max_sampling_rate = 1.0
        self.adjustment_interval = 5.0
        
        self._adjustment_thread = threading.Thread(
            target=self._adjustment_loop,
            daemon=True,
            name="SamplingAdjustmentThread"
        )
        self._adjustment_thread.start()
    
    def _adjustment_loop(self) -> None:
        """Loop de ajuste."""
        import time
        
        while not self._stop_event.is_set():
            try:
                time.sleep(self.adjustment_interval)
                self._adjust_sampling_rate()
            except Exception as e:
                print(f"Erro no ajuste de sampling: {e}", file=sys.stderr)
    
    def _adjust_sampling_rate(self) -> None:
        """Ajusta sampling rate."""
        queue_usage = self.queue.qsize() / self.queue.maxsize if self.queue.maxsize > 0 else 0
        
        if queue_usage > 0.7:
            self.sampling_rate = max(self.min_sampling_rate, self.sampling_rate * 0.5)
        elif queue_usage < 0.3:
            self.sampling_rate = min(self.max_sampling_rate, self.sampling_rate * 1.2)
    
    def close(self) -> None:
        """Para o handler."""
        super().close()
        
        if self._adjustment_thread and self._adjustment_thread.is_alive():
            self._adjustment_thread.join(timeout=1.0)


# ============================================================================
# CONFIGURATION
# ============================================================================

class EventDrivenLoggingConfig:
    """Configuração para logging via Event Bus."""
    
    def __init__(
        self,
        enabled: bool = True,
        service_name: str = "raxy",
        event_name: str = "log.event",
        queue_size: int = 10000,
        batch_size: int = 1,
        flush_interval: float = 0.1,
        enable_fallback: bool = True,
        sampling_rate: float = 1.0,
        adaptive_sampling: bool = False,
        enable_aggregator: bool = True,
        aggregator_console: bool = True,
        aggregator_file: bool = False,
        aggregator_file_path: Optional[str] = None,
    ):
        self.enabled = enabled
        self.service_name = service_name
        self.event_name = event_name
        self.queue_size = queue_size
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.enable_fallback = enable_fallback
        self.sampling_rate = sampling_rate
        self.adaptive_sampling = adaptive_sampling
        self.enable_aggregator = enable_aggregator
        self.aggregator_console = aggregator_console
        self.aggregator_file = aggregator_file
        self.aggregator_file_path = aggregator_file_path


# ============================================================================
# SETUP HELPERS
# ============================================================================

def create_event_driven_logger(
    event_bus: IEventBus,
    logger_config: Optional[LoggerConfig] = None,
    event_config: Optional[EventDrivenLoggingConfig] = None
) -> RaxyLogger:
    """Cria logger configurado para usar Event Bus."""
    if logger_config is None:
        logger_config = LoggerConfig()
    
    if event_config is None:
        event_config = EventDrivenLoggingConfig()
    
    logger = RaxyLogger(config=logger_config)
    
    if event_config.enabled and event_bus:
        if event_config.adaptive_sampling:
            handler = AdaptiveSamplingHandler(
                event_bus=event_bus,
                service_name=event_config.service_name,
                event_name=event_config.event_name,
                level=logger_config.nivel_minimo_valor(),
                queue_size=event_config.queue_size,
                batch_size=event_config.batch_size,
                flush_interval=event_config.flush_interval,
                enable_fallback=event_config.enable_fallback
            )
        else:
            handler = EventBusLogHandler(
                event_bus=event_bus,
                service_name=event_config.service_name,
                event_name=event_config.event_name,
                level=logger_config.nivel_minimo_valor(),
                queue_size=event_config.queue_size,
                batch_size=event_config.batch_size,
                flush_interval=event_config.flush_interval,
                enable_fallback=event_config.enable_fallback,
                sampling_rate=event_config.sampling_rate
            )
        
        logger.add_handler(handler)
    
    return logger


def create_log_aggregator(
    event_bus: IEventBus,
    logger: Optional[ILoggingService] = None,
    event_config: Optional[EventDrivenLoggingConfig] = None
):
    """Cria agregador de logs."""
    from raxy.core.events.event_logging import LogAggregator
    
    if event_config is None:
        event_config = EventDrivenLoggingConfig()
    
    aggregator = LogAggregator(
        event_bus=event_bus,
        logger=logger,
        enable_console=event_config.aggregator_console,
        enable_file=event_config.aggregator_file,
        log_file=event_config.aggregator_file_path,
        min_level=20
    )
    
    return aggregator


def setup_event_driven_logging(
    event_bus: IEventBus,
    logger_config: Optional[LoggerConfig] = None,
    event_config: Optional[EventDrivenLoggingConfig] = None,
    setup_aggregator: bool = True
):
    """Setup completo do sistema de logging via Event Bus."""
    if event_config is None:
        event_config = EventDrivenLoggingConfig()
    
    logger = create_event_driven_logger(
        event_bus=event_bus,
        logger_config=logger_config,
        event_config=event_config
    )
    
    aggregator = None
    if setup_aggregator and event_config.enable_aggregator:
        aggregator = create_log_aggregator(
            event_bus=event_bus,
            logger=None,
            event_config=event_config
        )
    
    return logger, aggregator


# ============================================================================
# HELPERS
# ============================================================================

def create_level_filter(min_level: int):
    """Cria filtro baseado em nível mínimo."""
    def filter_func(data: dict) -> bool:
        return data.get('level', 20) >= min_level
    return filter_func


def create_service_filter(*services: str):
    """Cria filtro baseado em nomes de serviço."""
    service_set = set(services)
    def filter_func(data: dict) -> bool:
        return data.get('service', '') in service_set
    return filter_func


def create_tag_filter(*tags: str):
    """Cria filtro baseado em tags."""
    tag_set = set(tags)
    def filter_func(data: dict) -> bool:
        event_tags = set(data.get('tags', []))
        return bool(tag_set & event_tags)
    return filter_func


def create_hostname_enricher():
    """Cria enricher que adiciona hostname."""
    hostname = socket.gethostname()
    def enricher_func(data: dict) -> dict:
        enriched = data.copy()
        context = enriched.get('context', {})
        context['hostname'] = hostname
        enriched['context'] = context
        return enriched
    return enricher_func


def create_pid_enricher():
    """Cria enricher que adiciona PID."""
    pid = os.getpid()
    def enricher_func(data: dict) -> dict:
        enriched = data.copy()
        context = enriched.get('context', {})
        context['pid'] = pid
        enriched['context'] = context
        return enriched
    return enricher_func


def create_environment_enricher():
    """Cria enricher que adiciona ambiente."""
    environment = os.getenv('ENVIRONMENT', 'development')
    def enricher_func(data: dict) -> dict:
        enriched = data.copy()
        context = enriched.get('context', {})
        context['environment'] = environment
        enriched['context'] = context
        return enriched
    return enricher_func
