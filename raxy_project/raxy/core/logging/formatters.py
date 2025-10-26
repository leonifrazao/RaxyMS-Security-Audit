"""
Formatadores para mensagens de log.

Define diferentes formatadores para diversos outputs (console, arquivo, JSON, etc).
"""

from __future__ import annotations

import json
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from raxy.core.config import LEVEL_NAMES


class LogFormatter(ABC):
    """
    Interface base para formatadores de log.
    
    Define o contrato para formatação de mensagens de log
    em diferentes formatos e destinos.
    """
    
    @abstractmethod
    def format(
        self,
        level: int,
        message: str,
        timestamp: datetime,
        context: Dict[str, Any],
        exception: Optional[Exception] = None
    ) -> str:
        """
        Formata uma mensagem de log.
        
        Args:
            level: Nível do log (numérico)
            message: Mensagem principal
            timestamp: Timestamp do evento
            context: Contexto e metadados
            exception: Exceção capturada (se houver)
            
        Returns:
            str: Mensagem formatada
        """
        pass


class ConsoleFormatter(LogFormatter):
    """
    Formatador para saída no console.
    
    Formata mensagens com cores e símbolos para melhor
    visualização no terminal.
    """
    
    # Mapeamento de cores ANSI
    COLORS = {
        10: '\033[90m',   # DEBUG - Cinza
        20: '\033[94m',   # INFO - Azul
        25: '\033[92m',   # SUCCESS - Verde
        30: '\033[93m',   # WARNING - Amarelo
        40: '\033[91m',   # ERROR - Vermelho
        50: '\033[95m',   # CRITICAL - Magenta
    }
    
    # Símbolos por nível
    SYMBOLS = {
        10: '🐛',  # DEBUG
        20: 'ℹ️',   # INFO
        25: '✅',  # SUCCESS
        30: '⚠️',   # WARNING
        40: '❌',  # ERROR
        50: '💀',  # CRITICAL
    }
    
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    def __init__(self, use_colors: bool = True, show_time: bool = True, 
                 show_location: bool = True, compact: bool = False):
        """
        Inicializa o formatador.
        
        Args:
            use_colors: Se deve usar cores ANSI
            show_time: Se deve mostrar timestamp
            show_location: Se deve mostrar arquivo/linha
            compact: Se deve usar formato compacto
        """
        self.use_colors = use_colors
        self.show_time = show_time
        self.show_location = show_location
        self.compact = compact
    
    def format(
        self,
        level: int,
        message: str,
        timestamp: datetime,
        context: Dict[str, Any],
        exception: Optional[Exception] = None
    ) -> str:
        """Formata mensagem para console."""
        parts = []
        
        # Determina cor
        color = self.COLORS.get(level, '') if self.use_colors else ''
        is_success = level == 25  # Nível SUCCESS
        
        # Símbolo
        symbol = self.SYMBOLS.get(level, '')
        if symbol and not self.compact:
            parts.append(f"{symbol} ")
        
        # Timestamp (sem cor para não interferir)
        if self.show_time:
            time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            if self.use_colors:
                parts.append(f"{self.DIM}{time_str}{self.RESET} ")
            else:
                parts.append(f"{time_str} ")
        
        # Inicia cor para o resto da linha (se for sucesso, verde em tudo)
        if self.use_colors:
            parts.append(color)
        
        # Nível
        level_name = LEVEL_NAMES.get(level, 'UNKNOWN').ljust(8)
        if self.use_colors:
            parts.append(f"{self.BOLD}{level_name}{self.RESET}{color}")
        else:
            parts.append(level_name)
        
        # Localização
        if self.show_location and not self.compact:
            file_info = context.get('file', '')
            line_info = context.get('line', '')
            func_info = context.get('function', '')
            
            if file_info or line_info or func_info:
                location = f" [{file_info}:{line_info}:{func_info}]"
                parts.append(location)
        
        # Separador
        parts.append(" | ")
        
        # Mensagem principal
        parts.append(message)
        
        # Contexto adicional (compacto)
        if self.compact and context:
            # Filtra campos internos
            extra = {k: v for k, v in context.items() 
                    if not k.startswith('_') and k not in ['file', 'line', 'function', 'class', 'module']}
            if extra:
                parts.append(f" | {self._format_context(extra)}")
        
        # Reset de cor
        if self.use_colors:
            parts.append(self.RESET)
        
        # Exceção
        if exception:
            parts.append('\n')
            parts.append(self._format_exception(exception))
        
        return ''.join(parts)
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Formata contexto de forma compacta."""
        items = []
        for key, value in context.items():
            if isinstance(value, str) and len(value) > 50:
                value = value[:47] + '...'
            items.append(f"{key}={repr(value)}")
        return ', '.join(items)
    
    def _format_exception(self, exception: Exception) -> str:
        """Formata exceção com traceback."""
        lines = ['Exception Details:']
        lines.append('-' * 40)
        
        tb_lines = traceback.format_exception(
            type(exception), exception, exception.__traceback__
        )
        lines.extend(tb_lines)
        
        if self.use_colors:
            # Adiciona cor vermelha ao traceback
            return self.COLORS[40] + '\n'.join(lines) + self.RESET
        
        return '\n'.join(lines)


class FileFormatter(LogFormatter):
    """
    Formatador para saída em arquivo.
    
    Formata mensagens em texto simples sem cores,
    otimizado para leitura em arquivos.
    """
    
    def __init__(self, include_context: bool = True, separator: str = ' | '):
        """
        Inicializa o formatador.
        
        Args:
            include_context: Se deve incluir contexto completo
            separator: Separador entre campos
        """
        self.include_context = include_context
        self.separator = separator
    
    def format(
        self,
        level: int,
        message: str,
        timestamp: datetime,
        context: Dict[str, Any],
        exception: Optional[Exception] = None
    ) -> str:
        """Formata mensagem para arquivo."""
        parts = []
        
        # Timestamp
        parts.append(timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        
        # Nível
        level_name = LEVEL_NAMES.get(level, 'UNKNOWN')
        parts.append(level_name.ljust(8))
        
        # Thread (se disponível)
        if 'thread' in context:
            parts.append(f"[{context['thread']}]")
        
        # Localização
        location_parts = []
        for key in ['module', 'class', 'function', 'line']:
            if key in context and context[key]:
                location_parts.append(str(context[key]))
        
        if location_parts:
            parts.append(':'.join(location_parts))
        
        # Mensagem
        parts.append(message)
        
        # Contexto adicional
        if self.include_context:
            extra = {k: v for k, v in context.items()
                    if not k.startswith('_') and 
                    k not in ['file', 'line', 'function', 'class', 'module', 'thread']}
            if extra:
                context_str = ', '.join(f"{k}={v}" for k, v in extra.items())
                parts.append(f"[{context_str}]")
        
        result = self.separator.join(parts)
        
        # Exceção
        if exception:
            tb_lines = traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
            result += '\n' + ''.join(tb_lines)
        
        return result


class JSONFormatter(LogFormatter):
    """
    Formatador JSON para logs estruturados.
    
    Ideal para processamento automatizado e
    integração com sistemas de análise de logs.
    """
    
    def __init__(self, pretty: bool = False, include_traceback: bool = True):
        """
        Inicializa o formatador.
        
        Args:
            pretty: Se deve formatar JSON com indentação
            include_traceback: Se deve incluir traceback completo
        """
        self.pretty = pretty
        self.include_traceback = include_traceback
    
    def format(
        self,
        level: int,
        message: str,
        timestamp: datetime,
        context: Dict[str, Any],
        exception: Optional[Exception] = None
    ) -> str:
        """Formata mensagem como JSON."""
        log_dict = {
            'timestamp': timestamp.isoformat(),
            'level': level,
            'level_name': LEVEL_NAMES.get(level, 'UNKNOWN'),
            'message': message,
        }
        
        # Adiciona contexto
        if context:
            # Separa campos de localização
            location = {}
            extra = {}
            
            for key, value in context.items():
                if key in ['file', 'path', 'line', 'function', 'class', 'module']:
                    location[key] = value
                elif not key.startswith('_'):
                    extra[key] = self._serialize_value(value)
            
            if location:
                log_dict['location'] = location
            if extra:
                log_dict['context'] = extra
        
        # Adiciona exceção
        if exception:
            log_dict['exception'] = {
                'type': exception.__class__.__name__,
                'message': str(exception),
            }
            
            if self.include_traceback:
                tb_lines = traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
                log_dict['exception']['traceback'] = tb_lines
        
        # Serializa para JSON
        if self.pretty:
            return json.dumps(log_dict, indent=2, ensure_ascii=False, default=str)
        else:
            return json.dumps(log_dict, ensure_ascii=False, default=str)
    
    def _serialize_value(self, value: Any) -> Any:
        """Serializa valor para JSON."""
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif hasattr(value, '__dict__'):
            return self._serialize_value(value.__dict__)
        else:
            return str(value)


class ErrorFormatter(LogFormatter):
    """
    Formatador especializado para erros.
    
    Fornece formatação detalhada de erros com
    informações de debug e contexto completo.
    """
    
    def format(
        self,
        level: int,
        message: str,
        timestamp: datetime,
        context: Dict[str, Any],
        exception: Optional[Exception] = None
    ) -> str:
        """Formata erro detalhadamente."""
        lines = []
        
        # Cabeçalho
        lines.append('=' * 80)
        lines.append(f"ERROR REPORT - {timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        lines.append('=' * 80)
        
        # Informações básicas
        lines.append(f"Level: {LEVEL_NAMES.get(level, 'UNKNOWN')}")
        lines.append(f"Message: {message}")
        
        # Localização
        lines.append("\nLocation:")
        for key in ['file', 'path', 'line', 'function', 'class', 'module']:
            if key in context and context[key]:
                lines.append(f"  {key.capitalize()}: {context[key]}")
        
        # Contexto
        if context:
            lines.append("\nContext:")
            for key, value in context.items():
                if not key.startswith('_') and key not in ['file', 'path', 'line', 'function', 'class', 'module']:
                    lines.append(f"  {key}: {value}")
        
        # Exceção
        if exception:
            lines.append("\nException Details:")
            lines.append(f"  Type: {exception.__class__.__module__}.{exception.__class__.__name__}")
            lines.append(f"  Message: {str(exception)}")
            
            lines.append("\nTraceback:")
            tb_lines = traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
            lines.extend(tb_lines)
        
        lines.append('=' * 80)
        
        return '\n'.join(lines)


# Factory para criar formatadores
class FormatterFactory:
    """Factory para criação de formatadores."""
    
    FORMATTERS = {
        'console': ConsoleFormatter,
        'file': FileFormatter,
        'json': JSONFormatter,
        'error': ErrorFormatter,
    }
    
    @classmethod
    def create(cls, formatter_type: str, **kwargs) -> LogFormatter:
        """
        Cria um formatador.
        
        Args:
            formatter_type: Tipo do formatador
            **kwargs: Argumentos para o formatador
            
        Returns:
            LogFormatter: Instância do formatador
            
        Raises:
            ValueError: Se tipo inválido
        """
        from raxy.core.exceptions import InvalidFormatterException
        
        formatter_class = cls.FORMATTERS.get(formatter_type)
        if not formatter_class:
            raise InvalidFormatterException(
                f"Tipo de formatador inválido: {formatter_type}",
                details={"formatter_type": formatter_type}
            )
        
        return formatter_class(**kwargs)
