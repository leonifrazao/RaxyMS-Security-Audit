"""
Configuração do executor em lote.

Define todas as configurações relacionadas à execução em lote de tarefas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .base import BaseConfig


@dataclass
class ExecutorConfig(BaseConfig):
    """
    Configuração para o executor em lote.
    
    Attributes:
        users_file: Arquivo com lista de usuários
        actions: Ações a serem executadas
        max_workers: Número máximo de workers paralelos
        use_proxies: Se deve usar proxies
        proxy_workers: Número de workers para teste de proxies
        proxy_auto_test: Se deve testar proxies automaticamente
        proxy_amounts: Quantidade de proxies a usar
        batch_size: Tamanho do lote de processamento
        retry_attempts: Número de tentativas em caso de erro
        retry_delay: Delay entre tentativas (segundos)
        timeout: Timeout para cada tarefa (segundos)
        api_error_words: Palavras que indicam erro na API
    """
    
    # Arquivos
    users_file: str = "users.txt"
    
    # Ações
    actions: List[str] = field(default_factory=lambda: [
        "login", 
        "flyout",
        "rewards", 
        "bing"
    ])
    
    # Workers e paralelismo
    max_workers: int = 2
    batch_size: int = 10
    
    # Proxies
    use_proxies: bool = True
    proxy_workers: int = 200
    proxy_auto_test: bool = True
    proxy_amounts: Optional[int] = None
    
    # Retry e timeout
    retry_attempts: int = 3
    retry_delay: float = 1.0
    timeout: int = 300  # 5 minutos
    
    # Detecção de erros
    api_error_words: List[str] = field(default_factory=lambda: [
        "captcha",
        "verifique",
        "verify", 
        "erro",
        "error",
        "unavailable",
        "blocked",
        "suspended"
    ])
    
    # Debug
    debug: bool = False
    
    def _validate_specific(self) -> None:
        """Validação específica do ExecutorConfig."""
        # Valida workers
        if self.max_workers < 1:
            raise ValueError("max_workers deve ser >= 1")
        
        if self.batch_size < 1:
            raise ValueError("batch_size deve ser >= 1")
        
        if self.proxy_workers < 1:
            raise ValueError("proxy_workers deve ser >= 1")
        
        # Valida retry
        if self.retry_attempts < 0:
            raise ValueError("retry_attempts deve ser >= 0")
        
        if self.retry_delay < 0:
            raise ValueError("retry_delay deve ser >= 0")
        
        if self.timeout < 0:
            raise ValueError("timeout deve ser >= 0")
        
        # Valida ações
        if not self.actions:
            raise ValueError("Pelo menos uma ação deve ser definida")
        
        valid_actions = {"login", "rewards", "bing", "flyout", "email"}
        invalid = set(self.actions) - valid_actions
        if invalid:
            raise ValueError(f"Ações inválidas: {invalid}")
    
    @classmethod
    def minimal(cls) -> ExecutorConfig:
        """
        Cria configuração mínima para testes.
        
        Returns:
            ExecutorConfig: Configuração mínima
        """
        return cls(
            max_workers=1,
            batch_size=1,
            use_proxies=False,
            retry_attempts=0,
            actions=["login"]
        )
