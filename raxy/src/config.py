"""Configuracoes compartilhadas e valores padrao da aplicacao."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import List, Optional

from .helpers import get_env_bool, get_env_int, get_env_list

# ---------------------------------------------------------------------------
# Bases compartilhadas
# ---------------------------------------------------------------------------

REWARDS_BASE_URL = os.getenv("REWARDS_BASE_URL", "https://login.live.com")

# Configuracao padrao aplicada ao decorator ``@browser`` do Botasaurus
BROWSER_KWARGS: dict = {
    "remove_default_browser_check_argument": True,
    "wait_for_complete_page_load": True,
    "block_images": True,
    "output": None,
    "tiny_profile": True,
}

# Valores padrao utilizados pelo executor em lote e APIs auxiliares
DEFAULT_ACTIONS: List[str] = ["login", "rewards", "solicitacoes"]
DEFAULT_API_ERROR_WORDS: List[str] = [
    "captcha",
    "verifique",
    "verify",
    "erro",
    "error",
    "unavailable",
]
DEFAULT_USERS_FILE = "users.txt"
DEFAULT_MAX_WORKERS = 1


@dataclass(slots=True)
class ExecutorConfig:
    """Configura parametros principais do processamento em lote."""

    users_file: str = DEFAULT_USERS_FILE
    actions: List[str] = field(default_factory=lambda: list(DEFAULT_ACTIONS))
    api_error_words: List[str] = field(default_factory=lambda: list(DEFAULT_API_ERROR_WORDS))
    max_workers: int = DEFAULT_MAX_WORKERS
    api_interactive_override: Optional[bool] = None

    @classmethod
    def from_env(cls, *, fallback_file: str | None = None) -> "ExecutorConfig":
        """Cria configuracao lendo variaveis de ambiente relevantes.

        Args:
            fallback_file: Caminho usado quando ``USERS_FILE`` estiver ausente.
        """

        arquivo = os.getenv("USERS_FILE", fallback_file or DEFAULT_USERS_FILE)
        actions_env = get_env_list("ACTIONS", padrao=DEFAULT_ACTIONS)
        actions = [acao.strip().lower() for acao in actions_env if acao.strip()]
        api_words = get_env_list(
            "REWARDS_API_ERROR_WORDS",
            padrao=DEFAULT_API_ERROR_WORDS,
        )
        max_workers_env = get_env_int("MAX_WORKERS")
        if max_workers_env is None:
            max_workers_env = get_env_int("RAXY_MAX_WORKERS")
        max_workers = max_workers_env if (max_workers_env and max_workers_env >= 1) else DEFAULT_MAX_WORKERS
        api_interactive = get_env_bool("RAXY_API_INTERACTIVE")

        return cls(
            users_file=arquivo,
            actions=actions or list(DEFAULT_ACTIONS),
            api_error_words=api_words or list(DEFAULT_API_ERROR_WORDS),
            max_workers=max_workers,
            api_interactive_override=api_interactive,
        )

    def api_interactivity(self) -> Optional[bool]:
        """Determina o modo interativo padrao da API considerando a configuracao."""

        if self.api_interactive_override is not None:
            return self.api_interactive_override
        return None if self.max_workers == 1 else False

    def clone(self) -> "ExecutorConfig":
        """Retorna uma nova instancia desacoplada das listas internas."""

        return ExecutorConfig(
            users_file=self.users_file,
            actions=list(self.actions),
            api_error_words=list(self.api_error_words),
            max_workers=self.max_workers,
            api_interactive_override=self.api_interactive_override,
        )


__all__ = [
    "BROWSER_KWARGS",
    "DEFAULT_ACTIONS",
    "DEFAULT_API_ERROR_WORDS",
    "DEFAULT_USERS_FILE",
    "DEFAULT_MAX_WORKERS",
    "ExecutorConfig",
    "REWARDS_BASE_URL",
]
