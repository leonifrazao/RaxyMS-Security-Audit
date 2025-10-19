"""
Controladores da API FastAPI.

Os controladores expõem a lógica de negócio através de endpoints HTTP REST.
Todos seguem o padrão BaseController para funcionalidades comuns.
"""

from .accounts_controller import router as accounts_router, AccountsController
from .auth_controller import router as auth_router, AuthController
from .executor_controller import router as executor_router
from .flyout_controller import router as flyout_router
from .logging_controller import router as logging_router
from .mailtm_controller import router as mailtm_router
from .proxy_controller import router as proxy_router
from .rewards_controller import router as rewards_router
from .suggestion_controller import router as suggestion_router

__all__ = [
    # Routers
    "accounts_router",
    "auth_router",
    "executor_router",
    "flyout_router",
    "logging_router",
    "mailtm_router",
    "proxy_router",
    "rewards_router",
    "suggestion_router",
    # Controllers
    "AccountsController",
    "AuthController",
]