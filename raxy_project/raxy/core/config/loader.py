"""
Loader para carregar configurações de diferentes fontes.

Suporta carregamento de variáveis de ambiente, arquivos JSON/YAML e valores padrão.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .app_config import AppConfig
from .executor_config import ExecutorConfig
from .proxy_config import ProxyConfig
from .api_config import APIConfig
from raxy.core.logging import LoggerConfig


class ConfigLoader:
    """
    Carregador de configurações.
    
    Carrega configurações de múltiplas fontes com ordem de prioridade:
    1. Variáveis de ambiente
    2. Arquivo de configuração
    3. Valores padrão
    """
    
    # Caminhos padrão de configuração
    DEFAULT_CONFIG_PATHS = [
        Path("config.json"),
        Path("config.yaml"),
        Path(".raxy.json"),
        Path(".raxy.yaml"),
        Path.home() / ".raxy" / "config.json",
        Path.home() / ".raxy" / "config.yaml",
        Path("/etc/raxy/config.json"),
        Path("/etc/raxy/config.yaml"),
    ]
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> AppConfig:
        """
        Carrega a configuração completa da aplicação.
        
        Args:
            config_path: Caminho específico para arquivo de configuração
            
        Returns:
            AppConfig: Configuração carregada
        """
        # 1. Carrega valores padrão
        config_data = cls._load_defaults()
        
        # 2. Carrega de arquivo se existir
        file_config = cls._load_from_file(config_path)
        if file_config:
            config_data = cls._merge_configs(config_data, file_config)
        
        # 3. Sobrescreve com variáveis de ambiente
        env_config = cls._load_from_env()
        config_data = cls._merge_configs(config_data, env_config)
        
        # 4. Cria configurações dos módulos
        config = cls._build_config(config_data)
        
        # 5. Valida configuração final
        config.validate()
        
        return config
    
    @classmethod
    def _load_defaults(cls) -> Dict[str, Any]:
        """Carrega valores padrão."""
        return {
            "app_name": "Raxy",
            "version": "2.0.0",
            "debug": False,
            "environment": "prod",
            "data_dir": "./data",
            "cache_dir": "./cache",
            "logs_dir": "./logs",
            "executor": {},
            "proxy": {},
            "api": {},
            "logging": {},
        }
    
    @classmethod
    def _load_from_file(cls, config_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """
        Carrega configuração de arquivo.
        
        Args:
            config_path: Caminho do arquivo
            
        Returns:
            Dicionário com configuração ou None
        """
        # Se path específico foi fornecido
        if config_path:
            if config_path.exists():
                return cls._read_config_file(config_path)
            return None
        
        # Procura em paths padrão
        for path in cls.DEFAULT_CONFIG_PATHS:
            if path.exists():
                try:
                    return cls._read_config_file(path)
                except Exception:
                    continue
        
        return None
    
    @classmethod
    def _read_config_file(cls, path: Path) -> Dict[str, Any]:
        """
        Lê arquivo de configuração.
        
        Args:
            path: Caminho do arquivo
            
        Returns:
            Dicionário com configuração
            
        Raises:
            ValueError: Se formato não suportado
        """
        if path.suffix == ".json":
            with open(path, 'r') as f:
                return json.load(f)
        
        elif path.suffix in [".yaml", ".yml"]:
            try:
                import yaml
                with open(path, 'r') as f:
                    return yaml.safe_load(f)
            except ImportError:
                raise ValueError("PyYAML não está instalado. Instale com: pip install pyyaml")
        
        else:
            raise ValueError(f"Formato de arquivo não suportado: {path.suffix}")
    
    @classmethod
    def _load_from_env(cls) -> Dict[str, Any]:
        """
        Carrega configuração de variáveis de ambiente.
        
        Returns:
            Dicionário com configuração
        """
        config = {}
        
        # App config
        if debug := os.getenv("RAXY_DEBUG"):
            config["debug"] = debug.lower() in ("true", "1", "yes", "on")
        
        if env := os.getenv("RAXY_ENVIRONMENT"):
            config["environment"] = env
        
        if data_dir := os.getenv("RAXY_DATA_DIR"):
            config["data_dir"] = data_dir
        
        if cache_dir := os.getenv("RAXY_CACHE_DIR"):
            config["cache_dir"] = cache_dir
        
        if logs_dir := os.getenv("RAXY_LOGS_DIR"):
            config["logs_dir"] = logs_dir
        
        # Executor config
        executor_config = {}
        if users_file := os.getenv("RAXY_USERS_FILE"):
            executor_config["users_file"] = users_file
        
        if max_workers := os.getenv("RAXY_MAX_WORKERS"):
            executor_config["max_workers"] = int(max_workers)
        
        if actions := os.getenv("RAXY_ACTIONS"):
            executor_config["actions"] = actions.split(",")
        
        if executor_config:
            config["executor"] = executor_config
        
        # Proxy config
        proxy_config = {}
        if use_proxies := os.getenv("RAXY_USE_PROXIES"):
            proxy_config["enabled"] = use_proxies.lower() in ("true", "1", "yes", "on")
        
        if proxy_sources := os.getenv("RAXY_PROXY_SOURCES"):
            proxy_config["sources"] = proxy_sources.split(",")
        
        if proxy_country := os.getenv("RAXY_PROXY_COUNTRY"):
            proxy_config["country"] = proxy_country
        
        if proxy_config:
            config["proxy"] = proxy_config
        
        # API config
        api_config = {}
        # Tenta primeiro sem prefixo (compatibilidade), depois com prefixo
        if supabase_url := os.getenv("SUPABASE_URL") or os.getenv("RAXY_SUPABASE_URL"):
            api_config["supabase_url"] = supabase_url
        
        if supabase_key := os.getenv("SUPABASE_KEY") or os.getenv("RAXY_SUPABASE_KEY"):
            api_config["supabase_key"] = supabase_key
        
        if api_config:
            config["api"] = api_config
        
        # Logging config
        logging_config = {}
        if log_level := os.getenv("RAXY_LOG_LEVEL"):
            logging_config["nivel_minimo"] = log_level
        
        if log_file := os.getenv("RAXY_LOG_FILE"):
            logging_config["arquivo_log"] = log_file
        
        if logging_config:
            config["logging"] = logging_config
        
        return config
    
    @classmethod
    def _merge_configs(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mescla duas configurações recursivamente.
        
        Args:
            base: Configuração base
            override: Configuração a sobrescrever
            
        Returns:
            Configuração mesclada
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Mescla recursiva para dicionários
                result[key] = cls._merge_configs(result[key], value)
            else:
                # Sobrescreve valor
                result[key] = value
        
        return result
    
    @classmethod
    def _build_config(cls, data: Dict[str, Any]) -> AppConfig:
        """
        Constrói objeto de configuração a partir do dicionário.
        
        Args:
            data: Dicionário com dados
            
        Returns:
            AppConfig: Configuração construída
        """
        # Extrai configurações dos módulos
        executor_data = data.pop("executor", {})
        proxy_data = data.pop("proxy", {})
        api_data = data.pop("api", {})
        logging_data = data.pop("logging", {})
        
        # Cria configurações dos módulos
        executor_config = ExecutorConfig.from_dict(executor_data)
        proxy_config = ProxyConfig.from_dict(proxy_data)
        api_config = APIConfig.from_dict(api_data)
        logging_config = LoggerConfig.from_env()  # Usa from_env do LoggerConfig
        
        # Atualiza com dados do arquivo/env se houver
        for key, value in logging_data.items():
            if hasattr(logging_config, key):
                setattr(logging_config, key, value)
        
        # Cria configuração principal
        return AppConfig.from_dict({
            **data,
            "executor": executor_config,
            "proxy": proxy_config,
            "api": api_config,
            "logging": logging_config,
        })
    
    @classmethod
    def save(cls, config: AppConfig, path: Path) -> None:
        """
        Salva configuração em arquivo.
        
        Args:
            config: Configuração a salvar
            path: Caminho do arquivo
            
        Raises:
            ValueError: Se formato não suportado
        """
        # Cria diretório se necessário
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Converte para dicionário
        config_dict = config.to_dict()
        
        # Salva baseado na extensão
        if path.suffix == ".json":
            with open(path, 'w') as f:
                json.dump(config_dict, f, indent=2, default=str)
        
        elif path.suffix in [".yaml", ".yml"]:
            try:
                import yaml
                with open(path, 'w') as f:
                    yaml.safe_dump(config_dict, f, default_flow_style=False)
            except ImportError:
                raise ValueError("PyYAML não está instalado. Instale com: pip install pyyaml")
        
        else:
            raise ValueError(f"Formato de arquivo não suportado: {path.suffix}")
