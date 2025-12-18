"""
Decorator de debug automático para logging de métodos.

Fornece logging automático de entrada/saída de métodos com contexto inteligente.
"""

from __future__ import annotations

import functools
import inspect
import time
from typing import Any, Callable, Optional, TypeVar

F = TypeVar('F', bound=Callable[..., Any])


def debug_log(
    enabled: bool = True,
    log_args: bool = True,
    log_result: bool = True,
    log_duration: bool = True,
    max_arg_length: int = 100,
) -> Callable[[F], F]:
    """
    Decorator que adiciona logging automático de debug em métodos.
    
    Loga automaticamente:
    - Entrada no método com argumentos
    - Saída do método com resultado
    - Duração da execução
    - Exceções (se ocorrerem)
    
    Args:
        enabled: Se o debug está habilitado (default: True)
        log_args: Se deve logar argumentos (default: True)
        log_result: Se deve logar resultado (default: True)
        log_duration: Se deve logar duração (default: True)
        max_arg_length: Tamanho máximo para representação de args (default: 100)
    
    Example:
        >>> @debug_log()
        >>> def obter_pontos(self, sessao):
        >>>     return 150
        
        # Logs gerados:
        # DEBUG: → obter_pontos(sessao=SessionManager(...))
        # DEBUG: ← obter_pontos() -> 150 [0.15s]
    
    Example com configuração:
        >>> @debug_log(log_args=False, log_result=False)
        >>> def processar_dados(self, data):
        >>>     return processed
        
        # Logs gerados:
        # DEBUG: → processar_dados()
        # DEBUG: ← processar_dados() [2.34s]
    """
    def decorator(func: F) -> F:
        if not enabled:
            return func
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Obtém logger (tenta do self/cls, senão usa global)
            logger = _get_logger(args)
            
            # Nome completo do método
            func_name = _get_func_full_name(func, args)
            
            # Formata argumentos
            args_str = ""
            if log_args:
                args_str = _format_arguments(args, kwargs, max_arg_length)
            
            # Log de entrada
            logger.debug(f"→ {func_name}({args_str})")
            
            # Executa método com timing
            start_time = time.time()
            exception_occurred = False
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Log de saída (sucesso)
                result_str = ""
                if log_result:
                    result_str = f" -> {_format_value(result, max_arg_length)}"
                
                duration_str = ""
                if log_duration:
                    duration_str = f" [{duration:.3f}s]"
                
                logger.debug(f"← {func_name}(){result_str}{duration_str}")
                
                return result
                
            except Exception as e:
                exception_occurred = True
                duration = time.time() - start_time
                
                # Log de saída (erro)
                duration_str = ""
                if log_duration:
                    duration_str = f" [{duration:.3f}s]"
                
                logger.debug(
                    f"✗ {func_name}() raised {type(e).__name__}: {str(e)[:100]}{duration_str}"
                )
                raise
        
        return wrapper  # type: ignore
    
    return decorator


def _get_logger(args: tuple) -> Any:
    """Obtém logger do self/cls ou usa global."""
    # Tenta obter do self (métodos de instância)
    if args and hasattr(args[0], 'logger'):
        return args[0].logger
    
    # Tenta obter do self._logger
    if args and hasattr(args[0], '_logger'):
        return args[0]._logger
    
    # Usa logger global (importação tardia para evitar circular)
    from raxy.core.logging.logger import RaxyLogger
    return RaxyLogger()


def _get_func_full_name(func: Callable, args: tuple) -> str:
    """Obtém nome completo do método (Class.method ou module.function)."""
    # Tenta obter nome da classe
    if args:
        obj = args[0]
        if hasattr(obj, '__class__'):
            class_name = obj.__class__.__name__
            return f"{class_name}.{func.__name__}"
    
    # Tenta obter do qualname
    if hasattr(func, '__qualname__'):
        return func.__qualname__
    
    # Fallback: apenas nome da função
    return func.__name__


def _format_arguments(args: tuple, kwargs: dict, max_length: int) -> str:
    """Formata argumentos para exibição."""
    parts = []
    
    # Ignora self/cls (primeiro argumento de métodos)
    start_idx = 1 if args and _is_instance_or_class(args[0]) else 0
    
    # Formata args posicionais
    for arg in args[start_idx:]:
        parts.append(_format_value(arg, max_length))
    
    # Formata kwargs
    for key, value in kwargs.items():
        parts.append(f"{key}={_format_value(value, max_length)}")
    
    return ", ".join(parts)


def _format_value(value: Any, max_length: int) -> str:
    """Formata valor para exibição limitada."""
    # Tipos simples
    if value is None:
        return "None"
    
    if isinstance(value, bool):
        return str(value)
    
    if isinstance(value, (int, float)):
        return str(value)
    
    if isinstance(value, str):
        if len(value) > max_length:
            return f'"{value[:max_length]}..."'
        return f'"{value}"'
    
    # Coleções
    if isinstance(value, (list, tuple)):
        count = len(value)
        type_name = type(value).__name__
        if count == 0:
            return f"{type_name}()"
        return f"{type_name}({count} items)"
    
    if isinstance(value, dict):
        count = len(value)
        if count == 0:
            return "dict()"
        return f"dict({count} keys)"
    
    # Objetos customizados
    class_name = type(value).__name__
    
    # Tenta usar __repr__ se for curto
    try:
        repr_str = repr(value)
        if len(repr_str) <= max_length:
            return repr_str
    except Exception:
        pass
    
    # Fallback: nome da classe
    return f"<{class_name}>"


def _is_instance_or_class(obj: Any) -> bool:
    """Verifica se objeto é instância ou classe (para ignorar self/cls)."""
    return (
        hasattr(obj, '__class__') and 
        not isinstance(obj, (str, int, float, bool, list, dict, tuple, set))
    )


# Decorator simplificado para uso rápido
def debug(func: F) -> F:
    """
    Versão simplificada do debug_log com configurações padrão.
    
    Example:
        >>> @debug
        >>> def meu_metodo(self, arg):
        >>>     return result
    """
    return debug_log()(func)


__all__ = ['debug_log', 'debug']
