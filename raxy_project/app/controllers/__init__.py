"""Routers expostos pela aplicação FastAPI."""

# profile_router foi removido
from .accounts_controller import router as accounts_router
from .auth_controller import router as auth_router
from .proxy_controller import router as proxy_router
from .rewards_controller import router as rewards_router
from .suggestion_controller import router as suggestion_router
from .executor_controller import router as executor_router
from .logging_controller import router as logging_router

__all__ = [
    "accounts_router",
    "auth_router",
    "proxy_router",
    "rewards_router",
    "suggestion_router",
    "executor_router",
    "logging_router",
]