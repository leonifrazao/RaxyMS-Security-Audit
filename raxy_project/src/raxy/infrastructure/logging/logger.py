"""
Logger principal do Raxy.

Implementa a interface ILoggingService e coordena todos os componentes
do sistema de logging (handlers, formatadores, contexto, etc).
"""

from __future__ import annotations

import sys
import traceback
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from raxy.infrastructure.config.config import LoggerConfig, LEVEL_VALUES
from .context import get_context, context_scope
from .formatters import ConsoleFormatter, FileFormatter, JSONFormatter, ErrorFormatter
from .handlers import (
    LogHandler, ConsoleHandler, FileHandler,
    BufferedHandler, AsyncHandler, MultiHandler
)


class RaxyLogger:
    """
    Implementação principal do sistema de logging.
    
    Coordena handlers, formatadores e contexto para prover
    um sistema de logging completo e eficiente.
    """
    
    def __init__(self, config: Optional[LoggerConfig] = None):
        """
        Inicializa o logger.
        
        Args:
            config: Configuração do logger
        """
        self.config = config or LoggerConfig()
        self.config.validate()
        
        self.handlers: List[LogHandler] = []
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Configura handlers baseado na configuração."""
        # Handler do console
        console_formatter = ConsoleFormatter(
            use_colors=self.config.usar_cores,
            show_time=self.config.mostrar_tempo,
            show_location=self.config.mostrar_localizacao,
            compact=not self.config.formato_detalhado
        )
        console_handler = ConsoleHandler(
            formatter=console_formatter,
            level=LEVEL_VALUES.get(self.config.nivel_minimo, 20),
            use_stderr=True
        )
        
        # Adiciona buffer se configurado
        if self.config.buffer_size > 0:
            console_handler = BufferedHandler(
                target_handler=console_handler,
                buffer_size=self.config.buffer_size
            )
        
        self.handlers.append(console_handler)
        
        # Handler de arquivo (se configurado)
        if self.config.arquivo_log:
            file_formatter = FileFormatter(include_context=True)
            file_handler = FileHandler(
                filename=self.config.arquivo_log,
                formatter=file_formatter,
                level=LEVEL_VALUES.get(self.config.nivel_minimo, 20),
                mode='w' if self.config.sobrescrever_arquivo else 'a'
            )
            
            # Torna assíncrono para não bloquear
            file_handler = AsyncHandler(
                target_handler=file_handler,
                queue_size=self.config.buffer_size * 2
            )
            
            self.handlers.append(file_handler)
        
        # Handler de erros (se configurado)
        if self.config.diretorio_erros:
            error_formatter = ErrorFormatter()
            error_file = self.config.diretorio_erros / f"{self.config.nome}_errors.log"
            error_handler = FileHandler(
                filename=error_file,
                formatter=error_formatter,
                level=LEVEL_VALUES.get("ERROR", 40),
                mode='a'
            )
            self.handlers.append(error_handler)
    
    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """
        Método interno para logging.
        
        Args:
            level: Nível do log
            message: Mensagem principal
            **kwargs: Dados adicionais
        """
        # Obtém valor numérico do nível
        level_value = LEVEL_VALUES.get(level.upper(), 20)
        
        # Obtém contexto atual
        ctx = get_context()
        caller_info = ctx.get_caller_info(depth=4)
        
        # Monta registro
        record = {
            'timestamp': datetime.now(),
            'level': level_value,
            'message': message,
            'context': {
                **ctx.to_dict(),
                **caller_info,
                **kwargs
            }
        }
        
        # Processa exceção se presente
        if 'exception' in kwargs:
            record['exception'] = kwargs['exception']
        elif 'exc_info' in kwargs and kwargs['exc_info']:
            exc_info = sys.exc_info()
            if exc_info[0]:
                record['exception'] = exc_info[1]
        
        # Envia para handlers
        for handler in self.handlers:
            try:
                handler.handle(record)
            except Exception as e:
                # Fallback para stderr
                print(f"Erro no handler de log: {e}", file=sys.stderr)
    
    # Implementação da interface ILoggingService
    
    def debug(self, mensagem: str, **dados: Any) -> None:
        """Registra mensagem de depuração."""
        self._log("DEBUG", mensagem, **dados)
    
    def info(self, mensagem: str, **dados: Any) -> None:
        """Registra mensagem informativa."""
        self._log("INFO", mensagem, **dados)
    
    def sucesso(self, mensagem: str, **dados: Any) -> None:
        """Registra mensagem de sucesso."""
        # Não adiciona emoji, o formatador já faz isso
        self._log("SUCCESS", mensagem, **dados)
    
    def aviso(self, mensagem: str, **dados: Any) -> None:
        """Registra uma advertência."""
        self._log("WARNING", mensagem, **dados)
    
    def erro(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro."""
        # Captura exceção atual se disponível
        if 'exc_info' not in dados:
            dados['exc_info'] = True
        
        self._log("ERROR", mensagem, **dados)
    
    def critico(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro crítico."""
        # Captura exceção atual se disponível
        if 'exc_info' not in dados:
            dados['exc_info'] = True
        
        self._log("CRITICAL", mensagem, **dados)
    
    def com_contexto(self, **dados: Any) -> ILoggingService:
        """
        Retorna um logger derivado com contexto adicional.
        
        Args:
            **dados: Contexto adicional
            
        Returns:
            ILoggingService: Logger com contexto
        """
        return ScopedLogger(self, dados)
    
    @contextmanager
    def etapa(self, titulo: str, **dados: Any):
        """
        Cria um contexto de execução para agrupar logs.
        
        Args:
            titulo: Título da etapa
            **dados: Dados adicionais
            
        Yields:
            None
        """
        # Mensagens padrão
        inicio = dados.pop('mensagem_inicial', f"Iniciando: {titulo}")
        sucesso = dados.pop('mensagem_sucesso', f"Concluído: {titulo}")
        falha = dados.pop('mensagem_falha', f"Falha: {titulo}")
        
        # Log de início
        self.info(inicio, operation=titulo, **dados)
        
        try:
            with context_scope(operation=titulo, **dados):
                yield
        except Exception as e:
            # Log de falha
            self.erro(falha, exception=e, **dados)
            raise
        else:
            # Log de sucesso
            self.sucesso(sucesso, **dados)
    
    def flush(self) -> None:
        """Força escrita de todos os buffers."""
        for handler in self.handlers:
            handler.flush()
    
    def close(self) -> None:
        """Fecha o logger e libera recursos."""
        for handler in self.handlers:
            handler.close()
        self.handlers.clear()
    
    def add_handler(self, handler: LogHandler) -> None:
        """
        Adiciona um handler.
        
        Args:
            handler: Handler a adicionar
        """
        self.handlers.append(handler)
    
    def remove_handler(self, handler: LogHandler) -> None:
        """
        Remove um handler.
        
        Args:
            handler: Handler a remover
        """
        if handler in self.handlers:
            handler.close()
            self.handlers.remove(handler)
    
    def set_level(self, level: str) -> None:
        """
        Define nível mínimo de log.
        
        Args:
            level: Nível mínimo (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        from raxy.core.exceptions import InvalidConfigException
        
        level_value = LEVEL_VALUES.get(level.upper())
        if level_value is None:
            raise InvalidConfigException(f"Nível inválido: {level}", details={"level": level})
        
        self.config.nivel_minimo = level.upper()
        
        # Atualiza handlers
        for handler in self.handlers:
            handler.level = level_value


class ScopedLogger:
    """
    Logger com contexto adicional.
    
    Wrapper que adiciona contexto fixo a todas as mensagens.
    """
    
    def __init__(self, parent: RaxyLogger, context: Dict[str, Any]):
        """
        Inicializa o logger com escopo.
        
        Args:
            parent: Logger pai
            context: Contexto adicional
        """
        self.parent = parent
        self.context = context
    
    def _merge_context(self, **dados: Any) -> Dict[str, Any]:
        """Mescla contexto com dados."""
        return {**self.context, **dados}
    
    def debug(self, mensagem: str, **dados: Any) -> None:
        """Registra mensagem de depuração."""
        self.parent.debug(mensagem, **self._merge_context(**dados))
    
    def info(self, mensagem: str, **dados: Any) -> None:
        """Registra mensagem informativa."""
        self.parent.info(mensagem, **self._merge_context(**dados))
    
    def sucesso(self, mensagem: str, **dados: Any) -> None:
        """Registra mensagem de sucesso."""
        self.parent.sucesso(mensagem, **self._merge_context(**dados))
    
    def aviso(self, mensagem: str, **dados: Any) -> None:
        """Registra uma advertência."""
        self.parent.aviso(mensagem, **self._merge_context(**dados))
    
    def erro(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro."""
        self.parent.erro(mensagem, **self._merge_context(**dados))
    
    def critico(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro crítico."""
        self.parent.critico(mensagem, **self._merge_context(**dados))
    
    def com_contexto(self, **dados: Any) -> ILoggingService:
        """Retorna um logger derivado com contexto adicional."""
        merged = self._merge_context(**dados)
        return ScopedLogger(self.parent, merged)
    
    @contextmanager
    def etapa(self, titulo: str, **dados: Any):
        """Cria um contexto de execução para agrupar logs."""
        with self.parent.etapa(titulo, **self._merge_context(**dados)):
            yield
