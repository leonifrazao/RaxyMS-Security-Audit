"""
Configuração de proxies.

Define configurações relacionadas ao uso e gerenciamento de proxies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .base import BaseConfig


@dataclass
class ProxyConfig(BaseConfig):
    """
    Configuração para gerenciamento de proxies.
    
    Attributes:
        enabled: Se o uso de proxies está habilitado
        sources: URLs para obter lista de proxies
        country: País preferencial para proxies
        max_concurrent_tests: Máximo de testes simultâneos
        test_timeout: Timeout para teste de proxy (segundos)
        test_url: URL para testar proxies
        rotation_strategy: Estratégia de rotação (round-robin, random, least-used)
        max_failures: Máximo de falhas antes de descartar proxy
        cache_duration: Duração do cache de proxies válidos (minutos)
        use_console: Se deve mostrar progresso no console
        min_speed_mbps: Velocidade mínima aceitável (Mbps)
    """
    
    enabled: bool = True
    
    # Fontes de proxies
    sources: List[str] = field(default_factory=lambda: [
        "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/ss_configs.txt"
    ])
    
    # Preferências
    country: str = "US"
    
    # Teste de proxies
    max_concurrent_tests: int = 200
    test_timeout: int = 10
    test_url: str = "https://www.bing.com"
    
    # Estratégia
    rotation_strategy: str = "round-robin"  # round-robin, random, least-used
    max_failures: int = 3
    
    # Cache
    cache_duration: int = 60  # minutos
    
    # Interface
    use_console: bool = True
    
    # Performance
    min_speed_mbps: Optional[float] = None
    
    def _validate_specific(self) -> None:
        """Validação específica do ProxyConfig."""
        # Valida estratégia
        valid_strategies = {"round-robin", "random", "least-used"}
        if self.rotation_strategy not in valid_strategies:
            raise ValueError(f"Estratégia inválida: {self.rotation_strategy}")
        
        # Valida timeouts e limites
        if self.max_concurrent_tests < 1:
            raise ValueError("max_concurrent_tests deve ser >= 1")
        
        if self.test_timeout < 1:
            raise ValueError("test_timeout deve ser >= 1")
        
        if self.max_failures < 1:
            raise ValueError("max_failures deve ser >= 1")
        
        if self.cache_duration < 0:
            raise ValueError("cache_duration deve ser >= 0")
        
        if self.min_speed_mbps is not None and self.min_speed_mbps <= 0:
            raise ValueError("min_speed_mbps deve ser > 0")
        
        # Valida URLs
        if self.enabled and not self.sources:
            raise ValueError("Pelo menos uma fonte de proxy deve ser definida")
    
    @classmethod
    def disabled(cls) -> ProxyConfig:
        """
        Cria configuração com proxies desabilitados.
        
        Returns:
            ProxyConfig: Configuração sem proxies
        """
        return cls(enabled=False)
