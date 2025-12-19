"""
Modelos de dados de configuração.

Define a estrutura tipada das configurações usando Dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from raxy.config.constants import (
    DEFAULT_SELECTORS, 
    LEVEL_VALUES, 
    VALID_ACTIONS, 
    VALID_ENVIRONMENTS
)
from raxy.config.validators import (
    ensure_path_exists,
    validate_choice,
    validate_not_empty,
    validate_positive_float,
    validate_positive_int,
    validate_subset,
    validate_type
)

try:
    from random_user_agent.params import OperatingSystem, SoftwareName
    _HAS_USER_AGENT = True
except ImportError:
    _HAS_USER_AGENT = False


@dataclass
class LoggerConfig:
    """Configuração para o sistema de logging."""
    
    nome: str = "raxy"
    nivel_minimo: str = "INFO"
    arquivo_log: Optional[Path] = None
    sobrescrever_arquivo: bool = False
    rotacao_arquivo: Optional[str] = "100 MB"
    retencao_arquivo: Optional[str] = "7 days"
    compressao_arquivo: Optional[str] = "zip"
    mostrar_tempo: bool = True
    mostrar_localizacao: bool = True
    usar_cores: bool = True
    formato_detalhado: bool = False
    diretorio_erros: Optional[Path] = None
    max_workers: int = 2
    buffer_size: int = 1000
    max_message_length: int = 10000
    
    def __post_init__(self):
        validate_choice(self.nivel_minimo.upper(), set(LEVEL_VALUES.keys()), "nivel_minimo")
        validate_positive_int(self.max_workers, "max_workers")
        validate_positive_int(self.buffer_size, "buffer_size", min_value=10)
        
        # Garante diretórios
        if self.arquivo_log:
            ensure_path_exists(self.arquivo_log)
        if self.diretorio_erros:
            ensure_path_exists(self.diretorio_erros)
    def validate(self):
        """Valida a configuração (compatibilidade com código legado)."""
        self.__post_init__()
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LoggerConfig:
        clean_data = {k: v for k, v in data.items() if k in cls.__annotations__}
        
        if "max_workers" in clean_data: validate_type(clean_data["max_workers"], int, "logging.max_workers")
        if "buffer_size" in clean_data: validate_type(clean_data["buffer_size"], int, "logging.buffer_size")
        if "usar_cores" in clean_data: validate_type(clean_data["usar_cores"], bool, "logging.usar_cores")

        # Conversão de paths
        if "arquivo_log" in clean_data and clean_data["arquivo_log"]:
            clean_data["arquivo_log"] = Path(clean_data["arquivo_log"])
        if "diretorio_erros" in clean_data and clean_data["diretorio_erros"]:
            clean_data["diretorio_erros"] = Path(clean_data["diretorio_erros"])
            
        return cls(**clean_data)


@dataclass
class ExecutorConfig:
    """Configuração para o executor de tarefas."""
    
    users_file: str = "users.txt"
    max_workers: int = 4
    actions: List[str] = field(default_factory=lambda: ["login", "flyout", "rewards", "bing"])
    retry_attempts: int = 2
    timeout: int = 300
    debug: bool = False

    def __post_init__(self):
        validate_positive_int(self.max_workers, "max_workers")
        validate_positive_int(self.retry_attempts, "retry_attempts", min_value=0)
        validate_positive_int(self.timeout, "timeout", min_value=0)
        validate_not_empty(self.actions, "actions")
        validate_subset(self.actions, VALID_ACTIONS, "actions")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutorConfig:
        clean = {k: v for k, v in data.items() if k in cls.__annotations__}
        
        if "max_workers" in clean: validate_type(clean["max_workers"], int, "executor.max_workers")
        if "retry_attempts" in clean: validate_type(clean["retry_attempts"], int, "executor.retry_attempts")
        if "timeout" in clean: validate_type(clean["timeout"], int, "executor.timeout")
        if "debug" in clean: validate_type(clean["debug"], bool, "executor.debug")
        if "actions" in clean: validate_type(clean["actions"], list, "executor.actions")
        
        return cls(**clean)


@dataclass
class ProxyConfig:
    """Configuração para o gerenciador de proxies."""
    
    enabled: bool = True
    sources: List[str] = field(default_factory=list)
    country: str = "US"
    use_console: bool = True
    auto_test: bool = True
    test_timeout: float = 10.0
    cache_filename: str = "proxy_cache.json"
    max_workers: int = 10

    def __post_init__(self):
        validate_positive_float(self.test_timeout, "test_timeout")
        validate_positive_int(self.max_workers, "max_workers", min_value=1)
        if self.enabled and not self.sources:
            # Default fallback source se habilitado mas vazio
            self.sources = ["https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-country/United_States.txt"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProxyConfig:
        clean = {k: v for k, v in data.items() if k in cls.__annotations__}
        
        if "enabled" in clean: validate_type(clean["enabled"], bool, "proxy.enabled")
        if "max_workers" in clean: validate_type(clean["max_workers"], int, "proxy.max_workers")
        if "use_console" in clean: validate_type(clean["use_console"], bool, "proxy.use_console")
        if "auto_test" in clean: validate_type(clean["auto_test"], bool, "proxy.auto_test")
        
        return cls(**clean)


@dataclass
class SessionConfig:
    """Configuração de sessão de navegação."""
    
    softwares_padrao: List[str] = field(default_factory=lambda: ["edge"])
    sistemas_padrao: List[str] = field(default_factory=lambda: ["windows", "linux", "macos"])
    ua_limit: int = 100
    max_login_attempts: int = 5
    selectors: Dict[str, str] = field(default_factory=dict)
    
    # URLs
    rewards_url: str = "https://rewards.bing.com/"
    bing_url: str = "https://www.bing.com"
    bing_flyout_url: str = "https://www.bing.com/rewards/panelflyout?channel=bingflyout&partnerId=BingRewards&isDarkMode=1&requestedLayout=onboarding&form=rwfobc"

    # Títulos de Janela (para detecção de estado)
    rewards_title: str = "microsoft rewards"
    verify_email_title: str = "verify your email"
    protect_account_title: str = "protect your account"

    def __post_init__(self):
        validate_positive_int(self.max_login_attempts, "max_login_attempts")
        validate_positive_int(self.ua_limit, "ua_limit")
        if not self.selectors:
            self.selectors = DEFAULT_SELECTORS.copy()
    
    def get_softwares_enums(self) -> List[Any]:
        if not _HAS_USER_AGENT: return []
        mapping = {
            "edge": SoftwareName.EDGE.value,
            "chrome": SoftwareName.CHROME.value,
            "firefox": SoftwareName.FIREFOX.value,
        }
        return [mapping.get(s.lower(), SoftwareName.EDGE.value) for s in self.softwares_padrao]
    
    def get_sistemas_enums(self) -> List[Any]:
        if not _HAS_USER_AGENT: return []
        mapping = {
            "windows": OperatingSystem.WINDOWS.value,
            "linux": OperatingSystem.LINUX.value,
            "macos": OperatingSystem.MACOS.value,
        }
        return [mapping.get(s.lower(), OperatingSystem.WINDOWS.value) for s in self.sistemas_padrao]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionConfig:
        clean = {k: v for k, v in data.items() if k in cls.__annotations__}
        
        if "ua_limit" in clean: validate_type(clean["ua_limit"], int, "session.ua_limit")
        if "max_login_attempts" in clean: validate_type(clean["max_login_attempts"], int, "session.max_login_attempts")
        if "softwares_padrao" in clean: validate_type(clean["softwares_padrao"], list, "session.softwares_padrao")
        if "sistemas_padrao" in clean: validate_type(clean["sistemas_padrao"], list, "session.sistemas_padrao")
        
        return cls(**clean)


@dataclass
class APIConfig:
    """Configurações para APIs externas."""
    
    supabase_url: str = ""
    supabase_key: str = ""
    findip_token: str = ""
    default_timeout: int = 30
    
    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> APIConfig:
        # Filtra apenas campos simples, sub-configs como rewards/bing não estão neste nível mais
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class AppConfig:
    """
    Configuração raiz da aplicação.
    Agrega todas as outras configurações.
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
    session: Optional[SessionConfig] = None

    def __post_init__(self):
        validate_choice(self.environment, VALID_ENVIRONMENTS, "environment")
        
        # Inicialização Lazy segura
        if self.executor is None: self.executor = ExecutorConfig()
        if self.proxy is None: self.proxy = ProxyConfig()
        if self.api is None: self.api = APIConfig()
        if self.logging is None: self.logging = LoggerConfig()
        if self.session is None: self.session = SessionConfig()
        
        # Garante diretórios base
        self.data_dir = ensure_path_exists(self.data_dir)
        self.cache_dir = ensure_path_exists(self.cache_dir)
        self.logs_dir = ensure_path_exists(self.logs_dir)

    @property
    def is_dev(self) -> bool:
        return self.environment == "dev"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppConfig:
        # Extrai sub-configs
        executor = ExecutorConfig.from_dict(data.get("executor", {}))
        proxy = ProxyConfig.from_dict(data.get("proxy", {}))
        api = APIConfig.from_dict(data.get("api", {}))
        logging = LoggerConfig.from_dict(data.get("logging", {}))
        session = SessionConfig.from_dict(data.get("session", {}))
        
        # Argumentos raiz (excluindo sub-configs já processadas)
        nested_keys = {"executor", "proxy", "api", "logging", "session"}
        root_args = {k: v for k, v in data.items() if k in cls.__annotations__ and k not in nested_keys}
        
        if "debug" in root_args: validate_type(root_args["debug"], bool, "debug")
        if "environment" in root_args: validate_type(root_args["environment"], str, "environment")
        
        # Conversão de paths raiz
        for field_name in ["data_dir", "cache_dir", "logs_dir"]:
            if root_args.get(field_name):
                root_args[field_name] = Path(root_args[field_name])

        instance = cls(
            **root_args,
            executor=executor,
            proxy=proxy,
            api=api,
            logging=logging,
            session=session
        )
        return instance
