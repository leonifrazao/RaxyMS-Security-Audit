"""Configuracoes compartilhadas e valores padrao da aplicacao."""

from __future__ import annotations

DEFAULT_ACTIONS = ["login", "rewards", "solicitacoes", "flyout"]
DEFAULT_API_ERROR_WORDS = [
    "captcha",
    "verifique",
    "verify",
    "erro",
    "error",
    "unavailable",
]
DEFAULT_USERS_FILE = "users.txt"
DEFAULT_MAX_WORKERS = 2