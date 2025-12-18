"""
Handlers para processamento e destino de logs.

Define diferentes handlers para enviar logs para diversos destinos
(console, arquivo, rede, etc) com suporte a buffering e async.
"""

from __future__ import annotations

import sys
import queue
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
from collections import deque

from .formatters import LogFormatter, ConsoleFormatter, FileFormatter


class LogHandler(ABC):
    """
    Interface base para handlers de log.
    
    Define o contrato para processamento e envio
    de mensagens de log para diferentes destinos.
    """
    
    def __init__(self, formatter: Optional[LogFormatter] = None,
                 level: int = 0, filters: Optional[List] = None):
        """
        Inicializa o handler.
        
        Args:
            formatter: Formatador a ser usado
            level: Nível mínimo para processar
            filters: Lista de filtros
        """
        self.formatter = formatter or ConsoleFormatter()
        self.level = level
        self.filters = filters or []
        self._lock = threading.RLock()
    
    def should_handle(self, level: int) -> bool:
        """
        Verifica se deve processar o nível.
        
        Args:
            level: Nível do log
            
        Returns:
            bool: True se deve processar
        """
        return level >= self.level
    
    def apply_filters(self, record: Dict[str, Any]) -> bool:
        """
        Aplica filtros ao registro.
        
        Args:
            record: Registro de log
            
        Returns:
            bool: True se passou pelos filtros
        """
        for filter_func in self.filters:
            if not filter_func(record):
                return False
        return True
    
    @abstractmethod
    def emit(self, record: Dict[str, Any]) -> None:
        """
        Emite o registro de log.
        
        Args:
            record: Registro a ser emitido
        """
        pass
    
    def handle(self, record: Dict[str, Any]) -> None:
        """
        Processa o registro de log.
        
        Args:
            record: Registro a ser processado
        """
        level = record.get('level', 0)
        
        # Verifica nível e filtros
        if not self.should_handle(level):
            return
        
        if not self.apply_filters(record):
            return
        
        # Emite o registro
        try:
            with self._lock:
                self.emit(record)
        except Exception as e:
            # Fallback para stderr em caso de erro
            print(f"Erro no handler: {e}", file=sys.stderr)
    
    def flush(self) -> None:
        """Força escrita de buffers pendentes."""
        pass
    
    def close(self) -> None:
        """Fecha o handler e libera recursos."""
        self.flush()


class ConsoleHandler(LogHandler):
    """
    Handler para saída no console.
    
    Envia logs formatados para stdout/stderr.
    """
    
    def __init__(self, stream=None, formatter: Optional[LogFormatter] = None,
                 level: int = 0, use_stderr: bool = False):
        """
        Inicializa o handler.
        
        Args:
            stream: Stream customizado (padrão: stdout/stderr)
            formatter: Formatador a usar
            level: Nível mínimo
            use_stderr: Se deve usar stderr ao invés de stdout
        """
        super().__init__(formatter or ConsoleFormatter(), level)
        self.stream = stream or (sys.stderr if use_stderr else sys.stdout)
    
    def emit(self, record: Dict[str, Any]) -> None:
        """Emite registro para console."""
        try:
            # Formata a mensagem
            formatted = self.formatter.format(
                level=record['level'],
                message=record['message'],
                timestamp=record['timestamp'],
                context=record.get('context', {}),
                exception=record.get('exception')
            )
            
            # Escreve no stream
            self.stream.write(formatted + '\n')
            self.stream.flush()
            
        except Exception as e:
            # Fallback simples
            print(f"Log error: {e}\nOriginal: {record.get('message', 'N/A')}", 
                  file=sys.stderr)
    
    def flush(self) -> None:
        """Força flush do stream."""
        if hasattr(self.stream, 'flush'):
            self.stream.flush()


class FileHandler(LogHandler):
    """
    Handler para saída em arquivo.
    
    Envia logs para arquivo com suporte a rotação.
    """
    
    def __init__(self, filename: str | Path, formatter: Optional[LogFormatter] = None,
                 level: int = 0, mode: str = 'a', encoding: str = 'utf-8',
                 max_bytes: int = 0, backup_count: int = 0):
        """
        Inicializa o handler.
        
        Args:
            filename: Caminho do arquivo
            formatter: Formatador a usar
            level: Nível mínimo
            mode: Modo de abertura ('a' ou 'w')
            encoding: Encoding do arquivo
            max_bytes: Tamanho máximo antes de rotacionar (0 = sem limite)
            backup_count: Número de backups a manter
        """
        super().__init__(formatter or FileFormatter(), level)
        self.filename = Path(filename)
        self.mode = mode
        self.encoding = encoding
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._file = None
        self._open()
    
    def _open(self) -> None:
        """Abre o arquivo para escrita."""
        # Cria diretório se necessário
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        
        # Abre arquivo
        self._file = open(self.filename, self.mode, encoding=self.encoding)
    
    def _should_rotate(self) -> bool:
        """Verifica se deve rotacionar o arquivo."""
        if self.max_bytes <= 0:
            return False
        
        try:
            return self.filename.stat().st_size >= self.max_bytes
        except:
            return False
    
    def _rotate(self) -> None:
        """Rotaciona o arquivo."""
        if self._file:
            self._file.close()
        
        # Renomeia arquivos antigos
        for i in range(self.backup_count - 1, 0, -1):
            old_name = self.filename.with_suffix(f'.{i}{self.filename.suffix}')
            new_name = self.filename.with_suffix(f'.{i+1}{self.filename.suffix}')
            
            if old_name.exists():
                if new_name.exists():
                    new_name.unlink()
                old_name.rename(new_name)
        
        # Renomeia arquivo atual
        if self.backup_count > 0:
            backup_name = self.filename.with_suffix(f'.1{self.filename.suffix}')
            if backup_name.exists():
                backup_name.unlink()
            if self.filename.exists():
                self.filename.rename(backup_name)
        
        # Reabre arquivo
        self._open()
    
    def emit(self, record: Dict[str, Any]) -> None:
        """Emite registro para arquivo."""
        if not self._file:
            self._open()
        
        # Verifica rotação
        if self._should_rotate():
            self._rotate()
        
        try:
            # Formata a mensagem
            formatted = self.formatter.format(
                level=record['level'],
                message=record['message'],
                timestamp=record['timestamp'],
                context=record.get('context', {}),
                exception=record.get('exception')
            )
            
            # Escreve no arquivo
            self._file.write(formatted + '\n')
            self._file.flush()
            
        except Exception as e:
            print(f"Erro ao escrever log: {e}", file=sys.stderr)
    
    def flush(self) -> None:
        """Força flush do arquivo."""
        if self._file:
            self._file.flush()
    
    def close(self) -> None:
        """Fecha o arquivo."""
        if self._file:
            self._file.close()
            self._file = None


class BufferedHandler(LogHandler):
    """
    Handler com buffer para otimizar performance.
    
    Acumula logs em memória antes de processar em batch.
    """
    
    def __init__(self, target_handler: LogHandler, buffer_size: int = 100,
                 flush_interval: float = 1.0):
        """
        Inicializa o handler.
        
        Args:
            target_handler: Handler de destino
            buffer_size: Tamanho do buffer
            flush_interval: Intervalo de flush em segundos
        """
        super().__init__(
            formatter=target_handler.formatter,
            level=target_handler.level,
            filters=target_handler.filters
        )
        self.target = target_handler
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.buffer: deque = deque(maxlen=buffer_size)
        self._timer = None
        self._start_timer()
    
    def _start_timer(self) -> None:
        """Inicia timer para flush automático."""
        if self._timer:
            self._timer.cancel()
        
        self._timer = threading.Timer(self.flush_interval, self._auto_flush)
        self._timer.daemon = True
        self._timer.start()
    
    def _auto_flush(self) -> None:
        """Flush automático por timer."""
        self.flush()
        self._start_timer()
    
    def emit(self, record: Dict[str, Any]) -> None:
        """Adiciona registro ao buffer."""
        self.buffer.append(record)
        
        # Flush se buffer cheio
        if len(self.buffer) >= self.buffer_size:
            self.flush()
    
    def flush(self) -> None:
        """Processa todos os registros do buffer."""
        with self._lock:
            while self.buffer:
                record = self.buffer.popleft()
                self.target.emit(record)
            
            self.target.flush()
    
    def close(self) -> None:
        """Fecha o handler."""
        if self._timer:
            self._timer.cancel()
        
        self.flush()
        self.target.close()


class AsyncHandler(LogHandler):
    """
    Handler assíncrono para processamento em thread separada.
    
    Evita bloqueio da aplicação durante operações de I/O.
    """
    
    def __init__(self, target_handler: LogHandler, queue_size: int = 1000):
        """
        Inicializa o handler.
        
        Args:
            target_handler: Handler de destino
            queue_size: Tamanho da fila
        """
        super().__init__(
            formatter=target_handler.formatter,
            level=target_handler.level,
            filters=target_handler.filters
        )
        self.target = target_handler
        self.queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._thread = None
        self._stop_event = threading.Event()
        self._start()
    
    def _start(self) -> None:
        """Inicia thread de processamento."""
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
    
    def _worker(self) -> None:
        """Worker que processa a fila."""
        while not self._stop_event.is_set():
            try:
                # Pega registro da fila (timeout para permitir shutdown)
                record = self.queue.get(timeout=0.1)
                
                # Processa o registro
                self.target.emit(record)
                
                # Marca como processado
                self.queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Erro no worker async: {e}", file=sys.stderr)
    
    def emit(self, record: Dict[str, Any]) -> None:
        """Adiciona registro à fila."""
        try:
            # Tenta adicionar sem bloquear
            self.queue.put_nowait(record)
        except queue.Full:
            # Se fila cheia, descarta log mais antigo
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(record)
            except:
                pass
    
    def flush(self) -> None:
        """Aguarda processamento de todos os registros."""
        self.queue.join()
        self.target.flush()
    
    def close(self) -> None:
        """Para o handler e thread."""
        # Sinaliza parada
        self._stop_event.set()
        
        # Aguarda thread terminar
        if self._thread:
            self._thread.join(timeout=2)
        
        # Fecha handler target
        self.target.close()


class MultiHandler(LogHandler):
    """
    Handler que distribui logs para múltiplos handlers.
    
    Permite enviar logs para vários destinos simultaneamente.
    """
    
    def __init__(self, handlers: List[LogHandler], level: int = 0):
        """
        Inicializa o handler.
        
        Args:
            handlers: Lista de handlers
            level: Nível mínimo
        """
        super().__init__(level=level)
        self.handlers = handlers
    
    def emit(self, record: Dict[str, Any]) -> None:
        """Emite para todos os handlers."""
        for handler in self.handlers:
            try:
                handler.handle(record)
            except Exception as e:
                print(f"Erro em handler: {e}", file=sys.stderr)
    
    def flush(self) -> None:
        """Flush em todos os handlers."""
        for handler in self.handlers:
            handler.flush()
    
    def close(self) -> None:
        """Fecha todos os handlers."""
        for handler in self.handlers:
            handler.close()
    
    def add_handler(self, handler: LogHandler) -> None:
        """Adiciona um handler."""
        self.handlers.append(handler)
    
    def remove_handler(self, handler: LogHandler) -> None:
        """Remove um handler."""
        if handler in self.handlers:
            self.handlers.remove(handler)
