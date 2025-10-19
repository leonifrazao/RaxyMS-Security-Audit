"""
Configuração principal da aplicação.

Agrega todas as configurações específicas em uma única classe.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from raxy.core.logging import LoggerConfig

from .base import BaseConfig
from .executor_config import ExecutorConfig
from .proxy_config import ProxyConfig
from .api_config import APIConfig


@dataclass
class AppConfig(BaseConfig):
    """
    Configuração principal do Raxy.
    
    Agrega todas as configurações específicas dos módulos
    em uma única classe centralizada.
    
    Attributes:
        app_name: Nome da aplicação
        version: Versão da aplicação
        debug: Modo debug ativado
        environment: Ambiente de execução (dev, staging, prod)
        data_dir: Diretório para dados da aplicação
        cache_dir: Diretório para cache
        logs_dir: Diretório para logs
        executor: Configuração do executor
        proxy: Configuração de proxies
        api: Configuração de APIs
        logging: Configuração de logging
    """
    
    # Identificação
    app_name: str = "Raxy"
    version: str = "2.0.0"
    
    # Ambiente
    debug: bool = False
    environment: str = "prod"  # dev, staging, prod
    
    # Diretórios
    data_dir: Path = Path("./data")
    cache_dir: Path = Path("./cache")
    logs_dir: Path = Path("./logs")
    
    # Configurações dos módulos
    executor: ExecutorConfig = None
    proxy: ProxyConfig = None
    api: APIConfig = None
    logging: LoggerConfig = None
    
    def __post_init__(self):
        """Inicializa configurações dos módulos se não fornecidas."""
        if self.executor is None:
            self.executor = ExecutorConfig()
        
        if self.proxy is None:
            self.proxy = ProxyConfig()
        
        if self.api is None:
            self.api = APIConfig()
        
        if self.logging is None:
            self.logging = LoggerConfig()
        
        # Garante que diretórios sejam Path
        self.data_dir = Path(self.data_dir)
        self.cache_dir = Path(self.cache_dir)
        self.logs_dir = Path(self.logs_dir)
    
    def _validate_specific(self) -> None:
        """Validação específica do AppConfig."""
        # Valida ambiente
        valid_environments = {"dev", "staging", "prod"}
        if self.environment not in valid_environments:
            raise ValueError(f"Ambiente inválido: {self.environment}")
        
        # Valida configurações dos módulos
        self.executor.validate()
        self.proxy.validate()
        self.api.validate()
        self.logging.validate()
        
        # Cria diretórios se não existirem
        for dir_path in [self.data_dir, self.cache_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def development(cls) -> AppConfig:
        """
        Cria configuração para ambiente de desenvolvimento.
        
        Returns:
            AppConfig: Configuração de desenvolvimento
        """
        return cls(
            debug=True,
            environment="dev",
            executor=ExecutorConfig.minimal(),
            proxy=ProxyConfig.disabled(),
            logging=LoggerConfig(nivel_minimo="DEBUG")
        )
    
    @classmethod
    def production(cls) -> AppConfig:
        """
        Cria configuração para ambiente de produção.
        
        Returns:
            AppConfig: Configuração de produção
        """
        return cls(
            debug=False,
            environment="prod",
            logging=LoggerConfig(nivel_minimo="INFO")
        )
    
    @property
    def is_development(self) -> bool:
        """Verifica se está em desenvolvimento."""
        return self.environment == "dev"
    
    @property
    def is_production(self) -> bool:
        """Verifica se está em produção."""
        return self.environment == "prod"
    
    def get_data_path(self, *parts: str) -> Path:
        """
        Constrói caminho dentro do diretório de dados.
        
        Args:
            *parts: Partes do caminho
            
        Returns:
            Path: Caminho completo
        """
        path = self.data_dir
        for part in parts:
            path = path / part
        return path
    
    def get_cache_path(self, *parts: str) -> Path:
        """
        Constrói caminho dentro do diretório de cache.
        
        Args:
            *parts: Partes do caminho
            
        Returns:
            Path: Caminho completo
        """
        path = self.cache_dir
        for part in parts:
            path = path / part
        return path
    
    def get_log_path(self, *parts: str) -> Path:
        """
        Constrói caminho dentro do diretório de logs.
        
        Args:
            *parts: Partes do caminho
            
        Returns:
            Path: Caminho completo
        """
        path = self.logs_dir
        for part in parts:
            path = path / part
        return path
