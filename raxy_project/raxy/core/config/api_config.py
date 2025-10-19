"""
Configuração de APIs externas.

Define configurações para integração com APIs externas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .base import BaseConfig


@dataclass
class APIConfig(BaseConfig):
    """
    Configuração para APIs externas.
    
    Attributes:
        supabase_url: URL do Supabase
        supabase_key: Chave de API do Supabase
        rewards_api_url: URL da API de Rewards
        bing_api_url: URL da API do Bing
        mail_tm_api_url: URL da API do Mail.tm
        request_timeout: Timeout padrão para requisições (segundos)
        max_retries: Número máximo de tentativas
        retry_backoff: Multiplicador de backoff para retry
        user_agent: User-Agent para requisições
        rate_limit_delay: Delay entre requisições para evitar rate limit (segundos)
    """
    
    # Supabase
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    
    # URLs de APIs
    rewards_api_url: str = "https://rewards.microsoft.com"
    bing_api_url: str = "https://www.bing.com"
    mail_tm_api_url: str = "https://api.mail.tm"
    
    # Timeouts e retries
    request_timeout: int = 30
    max_retries: int = 3
    retry_backoff: float = 1.5
    
    # Headers
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Rate limiting
    rate_limit_delay: float = 0.5
    
    def _validate_specific(self) -> None:
        """Validação específica do APIConfig."""
        # Valida timeouts
        if self.request_timeout < 1:
            raise ValueError("request_timeout deve ser >= 1")
        
        if self.max_retries < 0:
            raise ValueError("max_retries deve ser >= 0")
        
        if self.retry_backoff < 1.0:
            raise ValueError("retry_backoff deve ser >= 1.0")
        
        if self.rate_limit_delay < 0:
            raise ValueError("rate_limit_delay deve ser >= 0")
        
        # Valida URLs
        for field_name in ['rewards_api_url', 'bing_api_url', 'mail_tm_api_url']:
            url = getattr(self, field_name)
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"{field_name} deve começar com http:// ou https://")
    
    @property
    def has_supabase(self) -> bool:
        """Verifica se Supabase está configurado."""
        return bool(self.supabase_url and self.supabase_key)
