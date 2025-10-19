"""
Sistema de logging simplificado usando a nova arquitetura modular.

Este arquivo mantém compatibilidade com o código existente,
mas delega toda a funcionalidade para o novo sistema modular.
"""

from __future__ import annotations

from raxy.core.logging import get_logger, LoggerConfig

# Exporta instância singleton do logger
log = get_logger()

# Mantém compatibilidade com código existente
__all__ = ["log", "LoggerConfig", "get_logger"]
