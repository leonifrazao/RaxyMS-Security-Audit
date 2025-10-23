"""
Sistema de configuração centralizado do Raxy.

Carrega configurações do config.yaml com suporte a override por variáveis de ambiente.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from raxy.core.logging import LoggerConfig


@dataclass
class ExecutorConfig:
    """
    Configuração para o executor em lote.

    Attributes:
        users_file: Arquivo com lista de usuários
        actions: Ações a serem executadas
        max_workers: Número máximo de workers paralelos
        retry_attempts: Número de tentativas em caso de erro
        timeout: Timeout para cada tarefa (segundos)
        debug: Modo debug ativo
    """

    users_file: str = "users.txt"
    max_workers: int = 4
    actions: List[str] = field(
        default_factory=lambda: ["login", "flyout", "rewards", "bing"]
    )
    retry_attempts: int = 2
    timeout: int = 300
    debug: bool = False

    def __post_init__(self):
        """Valida a configuração."""
        if self.max_workers < 1:
            raise ValueError("max_workers deve ser >= 1")

        if self.retry_attempts < 0:
            raise ValueError("retry_attempts deve ser >= 0")

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
    def from_dict(cls, data: Dict[str, Any]) -> ExecutorConfig:
        """Cria instância a partir de dicionário."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class ProxyConfig:
    """
    Configuração para gerenciamento de proxies.

    Attributes:
        enabled: Se o uso de proxies está habilitado
        sources: Fontes de proxies
        country: País preferencial para proxies
        use_console: Se deve mostrar progresso no console
        auto_test: Se deve testar proxies automaticamente
        test_timeout: Timeout para teste de proxy (segundos)
    """

    enabled: bool = True
    sources: List[str] = field(default_factory=lambda: ["webshare", "proxylist"])
    country: str = "US"
    use_console: bool = True
    auto_test: bool = True
    test_timeout: float = 10.0

    def __post_init__(self):
        """Valida a configuração."""
        if self.test_timeout < 1:
            raise ValueError("test_timeout deve ser >= 1")

        if self.enabled and not self.sources:
            raise ValueError("Pelo menos uma fonte de proxy deve ser definida")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProxyConfig:
        """Cria instância a partir de dicionário."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class APIConfig:
    """
    Configuração para APIs externas.

    Attributes:
        supabase_url: URL do Supabase
        supabase_key: Chave de API do Supabase
    """

    supabase_url: str = ""
    supabase_key: str = ""

    @property
    def has_supabase(self) -> bool:
        """Verifica se Supabase está configurado."""
        return bool(self.supabase_url and self.supabase_key)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> APIConfig:
        """Cria instância a partir de dicionário."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class AppConfig:
    """
    Configuração principal do Raxy.

    Agrega todas as configurações específicas dos módulos.

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

    app_name: str = "Raxy"
    version: str = "2.0.0"
    debug: bool = False
    environment: str = "prod"

    data_dir: Optional[Path] = None
    cache_dir: Optional[Path] = None
    logs_dir: Optional[Path] = None

    executor: Optional[ExecutorConfig] = None
    proxy: Optional[ProxyConfig] = None
    api: Optional[APIConfig] = None
    logging: Optional[LoggerConfig] = None

    def __post_init__(self):
        """Inicializa configurações dos módulos e valida."""
        # Inicializa subconfigs se None
        if self.executor is None:
            self.executor = ExecutorConfig()

        if self.proxy is None:
            self.proxy = ProxyConfig()

        if self.api is None:
            self.api = APIConfig()

        if self.logging is None:
            self.logging = LoggerConfig()

        # Converte e expande paths
        if self.data_dir is not None:
            self.data_dir = Path(self.data_dir).expanduser().resolve()
            self.data_dir.mkdir(parents=True, exist_ok=True)

        if self.cache_dir is not None:
            self.cache_dir = Path(self.cache_dir).expanduser().resolve()
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        if self.logs_dir is not None:
            self.logs_dir = Path(self.logs_dir).expanduser().resolve()
            self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Valida ambiente
        valid_environments = {"dev", "staging", "prod"}
        if self.environment not in valid_environments:
            raise ValueError(
                f"Ambiente inválido: {self.environment}. "
                f"Use um dos: {', '.join(valid_environments)}"
            )

    @property
    def is_development(self) -> bool:
        """Verifica se está em desenvolvimento."""
        return self.environment == "dev"

    @property
    def is_production(self) -> bool:
        """Verifica se está em produção."""
        return self.environment == "prod"

    def get_data_path(self, *parts: str) -> Optional[Path]:
        """Constrói caminho dentro do diretório de dados."""
        if self.data_dir is None:
            return None
        path = self.data_dir
        for part in parts:
            path = path / part
        return path

    def get_cache_path(self, *parts: str) -> Optional[Path]:
        """Constrói caminho dentro do diretório de cache."""
        if self.cache_dir is None:
            return None
        path = self.cache_dir
        for part in parts:
            path = path / part
        return path

    def get_log_path(self, *parts: str) -> Optional[Path]:
        """Constrói caminho dentro do diretório de logs."""
        if self.logs_dir is None:
            return None
        path = self.logs_dir
        for part in parts:
            path = path / part
        return path

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppConfig:
        """Cria instância a partir de dicionário."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class ConfigLoader:
    """
    Carregador de configurações do YAML com override por variáveis de ambiente.
    """

    DEFAULT_CONFIG_PATH = Path("config.yaml")

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> AppConfig:
        """
        Carrega a configuração completa da aplicação.

        Args:
            config_path: Caminho específico para arquivo de configuração

        Returns:
            AppConfig: Configuração carregada
        """
        # 1. Determina caminho do arquivo
        path = config_path or cls.DEFAULT_CONFIG_PATH

        # 2. Lê YAML se existir
        if path.exists():
            data = cls._read_yaml(path)
        else:
            data = {}

        # 3. Override com variáveis de ambiente
        data = cls._merge_env_vars(data)

        # 4. Constrói configuração
        return cls._build_config(data)

    @classmethod
    def _read_yaml(cls, path: Path) -> Dict[str, Any]:
        """Lê arquivo YAML."""
        try:
            import yaml

            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            raise ValueError(
                "PyYAML não está instalado. Instale com: pip install pyyaml"
            )

    @classmethod
    def _merge_env_vars(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sobrescreve valores com variáveis de ambiente."""
        # App level
        if debug := os.getenv("RAXY_DEBUG"):
            data["debug"] = debug.lower() in ("true", "1", "yes", "on")

        if env := os.getenv("RAXY_ENVIRONMENT"):
            data["environment"] = env

        if data_dir := os.getenv("RAXY_DATA_DIR"):
            data["data_dir"] = data_dir

        if cache_dir := os.getenv("RAXY_CACHE_DIR"):
            data["cache_dir"] = cache_dir

        if logs_dir := os.getenv("RAXY_LOGS_DIR"):
            data["logs_dir"] = logs_dir

        # Executor
        executor = data.setdefault("executor", {})
        if users_file := os.getenv("RAXY_USERS_FILE"):
            executor["users_file"] = users_file

        if max_workers := os.getenv("RAXY_MAX_WORKERS"):
            executor["max_workers"] = int(max_workers)

        if actions := os.getenv("RAXY_ACTIONS"):
            executor["actions"] = [a.strip() for a in actions.split(",")]

        # Proxy
        proxy = data.setdefault("proxy", {})
        if enabled := os.getenv("RAXY_PROXY_ENABLED"):
            proxy["enabled"] = enabled.lower() in ("true", "1", "yes", "on")

        if country := os.getenv("RAXY_PROXY_COUNTRY"):
            proxy["country"] = country

        # API (compatibilidade com e sem prefixo)
        api = data.setdefault("api", {})
        if supabase_url := os.getenv("SUPABASE_URL") or os.getenv("RAXY_SUPABASE_URL"):
            api["supabase_url"] = supabase_url

        if supabase_key := os.getenv("SUPABASE_KEY") or os.getenv("RAXY_SUPABASE_KEY"):
            api["supabase_key"] = supabase_key

        # Logging
        logging = data.setdefault("logging", {})
        if log_level := os.getenv("RAXY_LOG_LEVEL"):
            logging["nivel_minimo"] = log_level

        if log_file := os.getenv("RAXY_LOG_FILE"):
            logging["arquivo_log"] = log_file

        return data

    @classmethod
    def _build_config(cls, data: Dict[str, Any]) -> AppConfig:
        """Constrói objeto de configuração a partir do dicionário."""
        # Extrai seções dos módulos
        executor_data = data.pop("executor", {})
        proxy_data = data.pop("proxy", {})
        api_data = data.pop("api", {})
        logging_data = data.pop("logging", {})

        # Cria configurações dos módulos
        executor_config = ExecutorConfig.from_dict(executor_data)
        proxy_config = ProxyConfig.from_dict(proxy_data)
        api_config = APIConfig.from_dict(api_data)

        # LoggerConfig usa seu próprio from_env()
        logging_config = LoggerConfig.from_env()

        # Atualiza LoggerConfig com dados do YAML
        for key, value in logging_data.items():
            if hasattr(logging_config, key):
                # Converte paths se necessário
                if key in ("arquivo_log", "diretorio_erros") and value is not None:
                    value = Path(value)
                setattr(logging_config, key, value)

        # Cria configuração principal
        return AppConfig(
            **data,
            executor=executor_config,
            proxy=proxy_config,
            api=api_config,
            logging=logging_config,
        )


# Instância global de configuração
_config_instance: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """
    Obtém a configuração global da aplicação.

    Returns:
        AppConfig: Configuração global
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader.load()
    return _config_instance


def reload_config() -> AppConfig:
    """
    Recarrega a configuração da aplicação.

    Returns:
        AppConfig: Nova configuração carregada
    """
    global _config_instance
    _config_instance = ConfigLoader.load()
    return _config_instance


__all__ = [
    "ExecutorConfig",
    "ProxyConfig",
    "APIConfig",
    "AppConfig",
    "ConfigLoader",
    "get_config",
    "reload_config",
]
