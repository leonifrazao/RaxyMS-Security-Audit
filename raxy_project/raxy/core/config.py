"""
Sistema de configuração centralizado do Raxy.

Carrega configurações do config.yaml com suporte a override por variáveis de ambiente.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from raxy.core.logging import LoggerConfig


# ============================================================================
# CONSTANTES E CONFIGURAÇÕES GLOBAIS
# ============================================================================

# Ações válidas do sistema
VALID_ACTIONS: Set[str] = {"login", "rewards", "bing", "flyout", "email"}

# Ambientes válidos
VALID_ENVIRONMENTS: Set[str] = {"dev", "staging", "prod"}

# Seletores CSS padrão
DEFAULT_SELECTORS: Dict[str, str] = {
    # Login
    "email_input": "input[type='email'], #i0116",
    "password_input": "input[type='password'], #i0118",
    "submit_button": "button[type='submit'], #idSIButton9",
    # Verificação
    "email_verify_link": "#view > div > span:nth-child(6) > div > span",
    "skip_link": "a[id='iShowSkip']",
    "primary_button": "button[data-testid='primaryButton']",
    # Status
    "id_s_span": 'span[id="id_s"]',
    "role_presentation": "span[role='presentation']",
    # Rewards
    "join_now": 'a[class="joinNowText"]',
    "card_0": 'div[id="Card_0"]',
}


# ============================================================================
# FUNÇÕES AUXILIARES DE VALIDAÇÃO
# ============================================================================

def validate_positive_int(value: int, field_name: str, min_value: int = 1) -> None:
    """Valida se um inteiro é >= min_value."""
    from raxy.core.exceptions import ValidationException
    
    if value < min_value:
        raise ValidationException(f"{field_name} deve ser >= {min_value}", details={"value": value, "min_value": min_value})


def validate_positive_float(value: float, field_name: str, min_value: float = 1.0) -> None:
    """Valida se um float é >= min_value."""
    from raxy.core.exceptions import ValidationException
    
    if value < min_value:
        raise ValidationException(f"{field_name} deve ser >= {min_value}", details={"value": value, "min_value": min_value})


def validate_not_empty(value: List[Any], field_name: str) -> None:
    """Valida se uma lista não está vazia."""
    from raxy.core.exceptions import ValidationException
    
    if not value:
        raise ValidationException(f"{field_name} não pode estar vazio")


def validate_subset(items: List[str], valid_set: Set[str], field_name: str) -> None:
    """Valida se todos os itens estão no conjunto válido."""
    from raxy.core.exceptions import ValidationException
    
    invalid = set(items) - valid_set
    if invalid:
        raise ValidationException(f"{field_name} inválido(s): {invalid}", details={"invalid_items": list(invalid)})


def validate_choice(value: str, valid_choices: Set[str], field_name: str) -> None:
    """Valida se um valor está em um conjunto de escolhas válidas."""
    from raxy.core.exceptions import ValidationException
    
    if value not in valid_choices:
        raise ValidationException(
            f"{field_name} inválido: {value}. Use um dos: {', '.join(valid_choices)}",
            details={"value": value, "valid_choices": list(valid_choices)}
        )


def ensure_path_exists(path: Optional[Path]) -> Optional[Path]:
    """Garante que um diretório existe, criando se necessário."""
    if path is not None:
        resolved = Path(path).expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved
    return None


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
        validate_positive_int(self.max_workers, "max_workers")
        validate_positive_int(self.retry_attempts, "retry_attempts", min_value=0)
        validate_positive_int(self.timeout, "timeout", min_value=0)
        validate_not_empty(self.actions, "actions")
        validate_subset(self.actions, VALID_ACTIONS, "Ações")

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
        cache_filename: Nome do arquivo de cache de proxies
        cache_version: Versão do cache
    """

    enabled: bool = True
    sources: List[str] = field(default_factory=lambda: ["webshare", "proxylist"])
    country: str = "US"
    use_console: bool = True
    auto_test: bool = True
    test_timeout: float = 10.0
    cache_filename: str = "proxy_cache.json"
    cache_version: int = 1

    def __post_init__(self):
        """Valida a configuração."""
        validate_positive_float(self.test_timeout, "test_timeout")
        if self.enabled:
            validate_not_empty(self.sources, "sources de proxy")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProxyConfig:
        """Cria instância a partir de dicionário."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class RewardsAPIConfig:
    """
    Configuração específica para API de Rewards.
    
    Attributes:
        error_words: Palavras que indicam erro na resposta
    """
    error_words: List[str] = field(
        default_factory=lambda: ["captcha", "temporarily unavailable", "error", "blocked"]
    )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RewardsAPIConfig:
        """Cria instância a partir de dicionário."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class BingSuggestionAPIConfig:
    """
    Configuração específica para API de Bing Suggestion.
    
    Attributes:
        error_words: Palavras que indicam erro na resposta
    """
    error_words: List[str] = field(
        default_factory=lambda: ["captcha", "temporarily unavailable", "error", "blocked"]
    )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BingSuggestionAPIConfig:
        """Cria instância a partir de dicionário."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class MailTmAPIConfig:
    """
    Configuração específica para API Mail.tm.
    
    Attributes:
        max_wait_time: Tempo máximo de espera (segundos)
        poll_interval: Intervalo de polling (segundos)
    """
    max_wait_time: int = 300
    poll_interval: int = 2
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MailTmAPIConfig:
        """Cria instância a partir de dicionário."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class EventsConfig:
    """
    Configuração para Event Bus (Redis Pub/Sub).
    
    Attributes:
        enabled: Se o event bus está habilitado
        host: Host do Redis
        port: Porta do Redis
        db: Database do Redis
        password: Senha do Redis (opcional)
        prefix: Prefixo para canais de eventos
        account_events: Habilita eventos de conta
        rewards_events: Habilita eventos de rewards
        proxy_events: Habilita eventos de proxy
        session_events: Habilita eventos de sessão
    """
    enabled: bool = True
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    prefix: str = "raxy:events:"
    account_events: bool = True
    rewards_events: bool = True
    proxy_events: bool = True
    session_events: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EventsConfig:
        """Cria instância a partir de dicionário."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class APIConfig:
    """
    Configuração para APIs externas.

    Attributes:
        supabase_url: URL do Supabase
        supabase_key: Chave de API do Supabase
        default_timeout: Timeout padrão para APIs (segundos)
        rewards: Configuração da API de Rewards
        bing_suggestion: Configuração da API de Bing Suggestion
        mail_tm: Configuração da API Mail.tm
        
    Note:
        Para resiliência de microserviços (retry/circuit breaker), use os
        decorators nativos do Botasaurus (@browser, @request, @task) com:
        - max_retry: número de tentativas (padrão: 0)
        - retry_wait: tempo entre retries em segundos
        - raise_exception: se deve lançar exceção (padrão: False)
        - close_on_crash: comportamento em caso de crash (padrão: False)
        
        Exemplo:
            @browser(max_retry=5, retry_wait=10, raise_exception=True)
            def scrape_data(driver, data):
                ...
    """

    supabase_url: str = ""
    supabase_key: str = ""
    default_timeout: int = 30
    rewards: Optional[RewardsAPIConfig] = None
    bing_suggestion: Optional[BingSuggestionAPIConfig] = None
    mail_tm: Optional[MailTmAPIConfig] = None
    
    def __post_init__(self):
        """Inicializa sub-configurações de APIs."""
        if self.rewards is None:
            self.rewards = RewardsAPIConfig()
        if self.bing_suggestion is None:
            self.bing_suggestion = BingSuggestionAPIConfig()
        if self.mail_tm is None:
            self.mail_tm = MailTmAPIConfig()

    @property
    def has_supabase(self) -> bool:
        """Verifica se Supabase está configurado."""
        return bool(self.supabase_url and self.supabase_key)
    
    # Propriedades de compatibilidade com código legado
    @property
    def rewards_error_words(self) -> List[str]:
        """Compatibilidade: acesso a rewards error_words."""
        return self.rewards.error_words if self.rewards else []
    
    @property
    def bing_suggestion_error_words(self) -> List[str]:
        """Compatibilidade: acesso a bing_suggestion error_words."""
        return self.bing_suggestion.error_words if self.bing_suggestion else []
    
    @property
    def mail_tm_max_wait_time(self) -> int:
        """Compatibilidade: acesso a mail_tm max_wait_time."""
        return self.mail_tm.max_wait_time if self.mail_tm else 300
    
    @property
    def mail_tm_poll_interval(self) -> int:
        """Compatibilidade: acesso a mail_tm poll_interval."""
        return self.mail_tm.poll_interval if self.mail_tm else 2

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> APIConfig:
        """Cria instância a partir de dicionário."""
        # Extrai configurações de nível superior
        result = {k: v for k, v in data.items() 
                  if k in cls.__annotations__ and k not in ('rewards', 'bing_suggestion', 'mail_tm')}
        
        # Processa sub-configurações
        if "rewards" in data:
            result["rewards"] = RewardsAPIConfig.from_dict(data["rewards"])
        
        if "bing_suggestion" in data:
            result["bing_suggestion"] = BingSuggestionAPIConfig.from_dict(data["bing_suggestion"])
        
        if "mail_tm" in data:
            result["mail_tm"] = MailTmAPIConfig.from_dict(data["mail_tm"])
        
        return cls(**result)


@dataclass
class SessionConfig:
    """
    Configuração para gerenciamento de sessões.

    Attributes:
        softwares_padrao: Softwares padrão para User-Agent
        sistemas_padrao: Sistemas operacionais padrão
        ua_limit: Limite de User-Agent
        rewards_url: URL do Microsoft Rewards
        bing_url: URL do Bing
        bing_flyout_url: URL do Bing Flyout
        max_login_attempts: Número máximo de tentativas de login
        rewards_title: Título esperado da página de rewards
        verify_email_title: Título da página de verificação de email
        protect_account_title: Título da página de proteção de conta
        selectors: Seletores CSS para elementos da página
    """

    softwares_padrao: List[str] = field(default_factory=lambda: ["edge"])
    sistemas_padrao: List[str] = field(
        default_factory=lambda: ["windows", "linux", "macos"]
    )
    ua_limit: int = 100
    rewards_url: str = "https://rewards.bing.com/"
    bing_url: str = "https://www.bing.com"
    bing_flyout_url: str = (
        "https://www.bing.com/rewards/panelflyout?"
        "channel=bingflyout&partnerId=BingRewards&"
        "isDarkMode=1&requestedLayout=onboarding&form=rwfobc"
    )
    max_login_attempts: int = 5
    rewards_title: str = "microsoft rewards"
    verify_email_title: str = "verify your email"
    protect_account_title: str = "let's protect your account"
    selectors: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Valida a configuração."""
        validate_positive_int(self.max_login_attempts, "max_login_attempts")
        validate_positive_int(self.ua_limit, "ua_limit")
        
        # Define seletores padrão se não fornecidos
        if not self.selectors:
            self.selectors = DEFAULT_SELECTORS.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionConfig:
        """Cria instância a partir de dicionário."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class BingFlyoutConfig:
    """
    Configuração para o serviço BingFlyout.

    Attributes:
        timeout_short: Timeout curto (segundos)
        timeout_long: Timeout longo (segundos)
        max_wait_iterations: Número máximo de iterações de espera
    """

    timeout_short: int = 5
    timeout_long: int = 10
    max_wait_iterations: int = 10

    def __post_init__(self):
        """Valida a configuração."""
        validate_positive_int(self.timeout_short, "timeout_short")
        validate_positive_int(self.timeout_long, "timeout_long")
        validate_positive_int(self.max_wait_iterations, "max_wait_iterations")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BingFlyoutConfig:
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
        session: Configuração de sessão
        bingflyout: Configuração do BingFlyout
        events: Configuração do Event Bus (Redis)
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
    events: Optional[EventsConfig] = None
    bingflyout: Optional[BingFlyoutConfig] = None

    def __post_init__(self):
        """Inicializa configurações dos módulos e valida."""
        # Inicializa subconfigs se None
        self._init_subconfigs()
        
        # Configura e valida paths
        self._setup_paths()
        
        # Valida ambiente
        validate_choice(self.environment, VALID_ENVIRONMENTS, "environment")
    
    def _init_subconfigs(self) -> None:
        """Inicializa sub-configurações se não definidas."""
        if self.executor is None:
            self.executor = ExecutorConfig()
        if self.proxy is None:
            self.proxy = ProxyConfig()
        if self.api is None:
            self.api = APIConfig()
        if self.logging is None:
            self.logging = LoggerConfig()
        if self.session is None:
            self.session = SessionConfig()
        if self.bingflyout is None:
            self.bingflyout = BingFlyoutConfig()
        if self.events is None:
            self.events = EventsConfig()
    
    def _setup_paths(self) -> None:
        """Configura e valida diretórios."""
        self.data_dir = ensure_path_exists(self.data_dir)
        self.cache_dir = ensure_path_exists(self.cache_dir)
        self.logs_dir = ensure_path_exists(self.logs_dir)

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
    
    Responsabilidades:
    - Leitura de arquivos YAML
    - Merge de variáveis de ambiente
    - Construção de objetos de configuração
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
        path = config_path or cls.DEFAULT_CONFIG_PATH
        data = cls._load_yaml(path)
        data = cls._apply_env_overrides(data)
        return cls._build_config(data)
    
    @classmethod
    def _load_yaml(cls, path: Path) -> Dict[str, Any]:
        """Carrega dados do YAML ou retorna dict vazio."""
        if path.exists():
            return cls._read_yaml(path)
        return {}

    @classmethod
    def _read_yaml(cls, path: Path) -> Dict[str, Any]:
        """Lê arquivo YAML."""
        try:
            import yaml

            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except ImportError as e:
            from raxy.core.exceptions import DependencyException
            raise DependencyException(
                "PyYAML não está instalado. Instale com: pip install pyyaml",
                cause=e
            )

    @classmethod
    def _apply_env_overrides(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica overrides de variáveis de ambiente."""
        cls._apply_app_env_vars(data)
        cls._apply_executor_env_vars(data)
        cls._apply_proxy_env_vars(data)
        cls._apply_api_env_vars(data)
        cls._apply_logging_env_vars(data)
        return data
    
    @classmethod
    def _apply_app_env_vars(cls, data: Dict[str, Any]) -> None:
        """Aplica variáveis de ambiente do nível app."""
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
    
    @classmethod
    def _apply_executor_env_vars(cls, data: Dict[str, Any]) -> None:
        """Aplica variáveis de ambiente do executor."""
        executor = data.setdefault("executor", {})
        if users_file := os.getenv("RAXY_USERS_FILE"):
            executor["users_file"] = users_file
        if max_workers := os.getenv("RAXY_MAX_WORKERS"):
            executor["max_workers"] = int(max_workers)
        if actions := os.getenv("RAXY_ACTIONS"):
            executor["actions"] = [a.strip() for a in actions.split(",")]
    
    @classmethod
    def _apply_proxy_env_vars(cls, data: Dict[str, Any]) -> None:
        """Aplica variáveis de ambiente do proxy."""
        proxy = data.setdefault("proxy", {})
        if enabled := os.getenv("RAXY_PROXY_ENABLED"):
            proxy["enabled"] = enabled.lower() in ("true", "1", "yes", "on")
        if country := os.getenv("RAXY_PROXY_COUNTRY"):
            proxy["country"] = country
    
    @classmethod
    def _apply_api_env_vars(cls, data: Dict[str, Any]) -> None:
        """Aplica variáveis de ambiente das APIs (com compatibilidade)."""
        api = data.setdefault("api", {})
        # Suporta nomes com e sem prefixo RAXY_ por compatibilidade
        if supabase_url := os.getenv("SUPABASE_URL") or os.getenv("RAXY_SUPABASE_URL"):
            api["supabase_url"] = supabase_url
        if supabase_key := os.getenv("SUPABASE_KEY") or os.getenv("RAXY_SUPABASE_KEY"):
            api["supabase_key"] = supabase_key
    
    @classmethod
    def _apply_logging_env_vars(cls, data: Dict[str, Any]) -> None:
        """Aplica variáveis de ambiente do logging."""
        logging = data.setdefault("logging", {})
        if log_level := os.getenv("RAXY_LOG_LEVEL"):
            logging["nivel_minimo"] = log_level
        if log_file := os.getenv("RAXY_LOG_FILE"):
            logging["arquivo_log"] = log_file

    @classmethod
    def _build_config(cls, data: Dict[str, Any]) -> AppConfig:
        """Constrói objeto de configuração a partir do dicionário."""
        # Extrai seções dos módulos
        executor_data = data.pop("executor", {})
        proxy_data = data.pop("proxy", {})
        api_data = data.pop("api", {})
        logging_data = data.pop("logging", {})
        session_data = data.pop("session", {})
        bingflyout_data = data.pop("bingflyout", {})
        events_data = data.pop("events", {})

        # Cria configurações dos módulos
        executor_config = ExecutorConfig.from_dict(executor_data)
        proxy_config = ProxyConfig.from_dict(proxy_data)
        api_config = APIConfig.from_dict(api_data)
        session_config = SessionConfig.from_dict(session_data)
        events_config = EventsConfig.from_dict(events_data)
        bingflyout_config = BingFlyoutConfig.from_dict(bingflyout_data)

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
            session=session_config,
            bingflyout=bingflyout_config,
            events=events_config,
        )


# ============================================================================
# GERENCIAMENTO DE CONFIGURAÇÃO GLOBAL (SINGLETON)
# ============================================================================

_config_instance: Optional[AppConfig] = None
_config_lock = False  # Lock para prevenir modificações acidentais


def get_config(auto_load: bool = True) -> Optional[AppConfig]:
    """
    Obtém a configuração global da aplicação.
    
    Args:
        auto_load: Se True, carrega automaticamente se não existir

    Returns:
        AppConfig ou None: Configuração global (None se não carregada e auto_load=False)
        
    Example:
        >>> config = get_config()
        >>> print(config.executor.max_workers)
    """
    global _config_instance
    if _config_instance is None and auto_load:
        _config_instance = ConfigLoader.load()
    return _config_instance


def reload_config(config_path: Optional[Path] = None) -> AppConfig:
    """
    Força recarga da configuração da aplicação.
    
    Args:
        config_path: Caminho opcional para arquivo de configuração

    Returns:
        AppConfig: Nova configuração carregada
        
    Example:
        >>> config = reload_config(Path("custom_config.yaml"))
    """
    from raxy.core.exceptions import ConfigLockedError
    
    global _config_instance, _config_lock
    if _config_lock:
        raise ConfigLockedError(
            "Configuração está bloqueada. Use unlock_config() antes de recarregar."
        )
    _config_instance = ConfigLoader.load(config_path)
    return _config_instance


def set_config(config: AppConfig, force: bool = False) -> None:
    """
    Define uma nova configuração manualmente.
    
    Útil para testes ou para sobrescrever configurações em runtime.
    
    Args:
        config: Nova configuração a ser usada
        force: Se True, ignora o lock
        
    Example:
        >>> config = AppConfig(debug=True, environment="dev")
        >>> set_config(config)
    """
    from raxy.core.exceptions import ConfigLockedError
    
    global _config_instance, _config_lock
    if _config_lock and not force:
        raise ConfigLockedError(
            "Configuração está bloqueada. Use unlock_config() ou force=True."
        )
    _config_instance = config


def update_config(**kwargs) -> AppConfig:
    """
    Atualiza valores específicos da configuração de nível superior.
    
    Args:
        **kwargs: Valores a serem atualizados (apenas nível superior)
        
    Returns:
        AppConfig: Configuração atualizada
        
    Example:
        >>> update_config(debug=True, environment='dev')
        >>> 
        >>> # Para atualizar valores aninhados, acesse diretamente:
        >>> config = get_config()
        >>> config.executor.max_workers = 8
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader.load()
    
    for key, value in kwargs.items():
        if hasattr(_config_instance, key):
            setattr(_config_instance, key, value)
    
    return _config_instance


def reset_config() -> None:
    """
    Reseta a configuração para None, forçando recarga na próxima chamada.
    
    Útil para testes ou quando você quer garantir que a config seja
    recarregada do arquivo.
    
    Example:
        >>> reset_config()
        >>> config = get_config()  # Vai recarregar do YAML
    """
    global _config_instance, _config_lock
    if _config_lock:
        raise RuntimeError(
            "Configuração está bloqueada. Use unlock_config() antes de resetar."
        )
    _config_instance = None


def lock_config() -> None:
    """
    Bloqueia a configuração para prevenir modificações acidentais.
    
    Útil em ambientes de produção para garantir consistência.
    
    Example:
        >>> config = get_config()
        >>> lock_config()
        >>> # Agora reload_config() e reset_config() vão lançar erro
    """
    global _config_lock
    _config_lock = True


def unlock_config() -> None:
    """
    Desbloqueia a configuração.
    
    Example:
        >>> unlock_config()
        >>> reset_config()  # Agora funciona
    """
    global _config_lock
    _config_lock = False


def is_config_locked() -> bool:
    """Verifica se a configuração está bloqueada."""
    return _config_lock


__all__ = [
    # Constantes
    "VALID_ACTIONS",
    "VALID_ENVIRONMENTS",
    "DEFAULT_SELECTORS",
    # Funções de validação
    "validate_positive_int",
    "validate_positive_float",
    "validate_not_empty",
    "validate_subset",
    "validate_choice",
    "ensure_path_exists",
    # Classes de configuração
    "ExecutorConfig",
    "ProxyConfig",
    "RewardsAPIConfig",
    "BingSuggestionAPIConfig",
    "MailTmAPIConfig",
    "APIConfig",
    "SessionConfig",
    "BingFlyoutConfig",
    "AppConfig",
    "ConfigLoader",
    # Gerenciamento de configuração global
    "get_config",
    "reload_config",
    "set_config",
    "update_config",
    "reset_config",
    "lock_config",
    "unlock_config",
    "is_config_locked",
]
