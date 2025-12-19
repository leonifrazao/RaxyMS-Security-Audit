"""
Classe base para clientes de API.
"""

from __future__ import annotations

import json
from abc import ABC
from pathlib import Path
from typing import Any, Dict, Optional, List

from raxy.interfaces.services import ILoggingService


class BaseAPIClient(ABC):
    """
    Classe base para clientes de API.
    
    Fornece funcionalidades comuns:
    - Carregamento de templates JSON
    - Logger
    - Configurações básicas (base_url, timeout, error_words)
    
    As requisições HTTP devem usar SessionManagerService.execute_template()
    que já gerencia cookies, UA, proxy e retry.
    """
    
    TEMPLATES_DIR = Path(__file__).resolve().parent / "requests_templates"
    
    def __init__(
        self,
        base_url: str,
        logger: Optional[ILoggingService] = None,
        timeout: int = 30,
        error_words: Optional[List[str]] = None,
    ):
        """
        Inicializa o cliente de API.
        
        Args:
            base_url: URL base da API
            logger: Logger (opcional)
            timeout: Timeout em segundos
            error_words: Palavras que indicam erro na resposta
        """
        self.base_url = base_url.rstrip('/')
        self._logger = logger or self._get_logger()
        self.timeout = timeout
        self.error_words = tuple(word.lower() for word in (error_words or []))
    
    def _get_logger(self) -> ILoggingService:
        """Obtém logger padrão."""
        from raxy.core.logging import get_logger
        return get_logger()
    
    def load_template(self, template_name: str) -> Dict[str, Any]:
        """Carrega template JSON."""
        with open(self.TEMPLATES_DIR / template_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @property
    def logger(self) -> ILoggingService:
        """Logger."""
        return self._logger
