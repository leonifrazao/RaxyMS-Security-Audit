"""
Gerenciamento de contexto para logs.

Fornece funcionalidades para adicionar contexto aos logs,
permitindo rastreamento detalhado e correlação de eventos.
"""

from __future__ import annotations

import inspect
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass
class LogContext:
    """
    Contexto de execução para logs.
    
    Gerencia informações contextuais que são anexadas aos logs,
    permitindo melhor rastreabilidade e debugging.
    
    Attributes:
        correlation_id: ID único para correlacionar logs relacionados
        session_id: ID da sessão atual
        user_id: ID do usuário (se aplicável)
        operation: Operação sendo executada
        metadata: Metadados adicionais
        _local: Thread-local storage para contextos específicos
    """
    
    correlation_id: str = field(default_factory=lambda: str(uuid4())[:8])
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    operation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    _local: threading.local = field(default_factory=threading.local, repr=False)
    
    def set(self, **kwargs: Any) -> None:
        """
        Define valores no contexto.
        
        Args:
            **kwargs: Pares chave-valor para adicionar ao contexto
        """
        for key, value in kwargs.items():
            if value is not None:
                if hasattr(self, key) and not key.startswith('_'):
                    setattr(self, key, value)
                else:
                    self.metadata[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém valor do contexto.
        
        Args:
            key: Chave do valor
            default: Valor padrão se não encontrado
            
        Returns:
            Any: Valor encontrado ou default
        """
        if hasattr(self, key) and not key.startswith('_'):
            return getattr(self, key, default)
        return self.metadata.get(key, default)
    
    def clear(self, *keys: str) -> None:
        """
        Remove valores do contexto.
        
        Args:
            *keys: Chaves para remover. Se vazio, limpa tudo
        """
        if not keys:
            self.metadata.clear()
            self.session_id = None
            self.user_id = None
            self.operation = None
        else:
            for key in keys:
                if hasattr(self, key) and not key.startswith('_'):
                    setattr(self, key, None)
                self.metadata.pop(key, None)
    
    @contextmanager
    def scope(self, **kwargs: Any):
        """
        Context manager para escopo temporário.
        
        Args:
            **kwargs: Valores temporários para o contexto
            
        Yields:
            LogContext: Self com valores temporários
        """
        old_values = {}
        
        # Salva valores antigos
        for key, value in kwargs.items():
            old_values[key] = self.get(key)
        
        # Define novos valores
        self.set(**kwargs)
        
        try:
            yield self
        finally:
            # Restaura valores antigos
            for key, value in old_values.items():
                if value is None and key in self.metadata:
                    del self.metadata[key]
                else:
                    self.set(**{key: value})
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte contexto para dicionário.
        
        Returns:
            Dict[str, Any]: Representação em dicionário
        """
        result = {
            'correlation_id': self.correlation_id,
        }
        
        if self.session_id:
            result['session_id'] = self.session_id
        if self.user_id:
            result['user_id'] = self.user_id
        if self.operation:
            result['operation'] = self.operation
        
        # Adiciona metadados
        result.update(self.metadata)
        
        return result
    
    def get_caller_info(self, depth: int = 3) -> Dict[str, Any]:
        """
        Obtém informações sobre o chamador.
        
        Args:
            depth: Profundidade na pilha de chamadas
            
        Returns:
            Dict[str, Any]: Informações do chamador
        """
        try:
            frame = inspect.currentframe()
            if frame is None:
                return {}
            
            # Navega pelos frames
            for _ in range(depth):
                frame = frame.f_back
                if frame is None:
                    break
            
            if frame is None:
                return {}
            
            info = inspect.getframeinfo(frame)
            code = frame.f_code
            
            # Tenta obter a classe
            class_name = None
            if 'self' in frame.f_locals:
                class_name = frame.f_locals['self'].__class__.__name__
            elif 'cls' in frame.f_locals:
                class_name = frame.f_locals['cls'].__name__
            
            return {
                'file': Path(info.filename).name,
                'path': info.filename,
                'line': info.lineno,
                'function': code.co_name,
                'class': class_name,
                'module': inspect.getmodule(frame).__name__ if inspect.getmodule(frame) else None,
            }
            
        except Exception:
            return {}
        finally:
            # Limpa referência ao frame
            del frame
    
    def __repr__(self) -> str:
        """Representação string do contexto."""
        items = []
        
        if self.correlation_id:
            items.append(f"id={self.correlation_id}")
        if self.session_id:
            items.append(f"session={self.session_id}")
        if self.user_id:
            items.append(f"user={self.user_id}")
        if self.operation:
            items.append(f"op={self.operation}")
        if self.metadata:
            items.append(f"meta={len(self.metadata)}")
        
        return f"LogContext({', '.join(items)})"


class ContextManager:
    """
    Gerenciador global de contextos.
    
    Mantém um contexto por thread e permite herança de contextos.
    """
    
    def __init__(self):
        """Inicializa o gerenciador."""
        self._contexts: Dict[int, LogContext] = {}
        self._lock = threading.RLock()
        self._default_context = LogContext()
    
    def get_context(self) -> LogContext:
        """
        Obtém contexto da thread atual.
        
        Returns:
            LogContext: Contexto da thread ou default
        """
        thread_id = threading.get_ident()
        
        with self._lock:
            if thread_id not in self._contexts:
                # Cria novo contexto herdando do default
                self._contexts[thread_id] = LogContext(
                    correlation_id=self._default_context.correlation_id,
                    session_id=self._default_context.session_id,
                    user_id=self._default_context.user_id,
                    operation=self._default_context.operation,
                    metadata=dict(self._default_context.metadata)
                )
            
            return self._contexts[thread_id]
    
    def set_context(self, context: LogContext) -> None:
        """
        Define contexto para thread atual.
        
        Args:
            context: Contexto a ser definido
        """
        thread_id = threading.get_ident()
        
        with self._lock:
            self._contexts[thread_id] = context
    
    def clear_context(self) -> None:
        """Remove contexto da thread atual."""
        thread_id = threading.get_ident()
        
        with self._lock:
            self._contexts.pop(thread_id, None)
    
    def set_default(self, **kwargs: Any) -> None:
        """
        Define valores no contexto default.
        
        Args:
            **kwargs: Valores para o contexto default
        """
        with self._lock:
            self._default_context.set(**kwargs)
    
    @contextmanager
    def context_scope(self, **kwargs: Any):
        """
        Cria escopo temporário de contexto.
        
        Args:
            **kwargs: Valores temporários
            
        Yields:
            LogContext: Contexto com valores temporários
        """
        context = self.get_context()
        with context.scope(**kwargs):
            yield context


# Instância global do gerenciador
_context_manager = ContextManager()


def get_context() -> LogContext:
    """Obtém contexto atual."""
    return _context_manager.get_context()


def set_context(**kwargs: Any) -> None:
    """Define valores no contexto atual."""
    _context_manager.get_context().set(**kwargs)


@contextmanager
def context_scope(**kwargs: Any):
    """Cria escopo temporário de contexto."""
    with _context_manager.context_scope(**kwargs) as ctx:
        yield ctx
