"""Ponto de entrada FastAPI que atua como API Gateway para a biblioteca raxy."""

from __future__ import annotations

import uvicorn  # 1. Adicione esta linha
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from raxy.container import create_injector
from raxy.interfaces.services import IProxyService

from controllers import (
    accounts_router,
    auth_router,
    executor_router,
    logging_router,
    profile_router,
    proxy_router,
    rewards_router,
    suggestion_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia recursos globais ao iniciar/encerrar a API."""

    injector = create_injector()
    app.state.injector = injector
    app.state.sessions = {}
    try:
        yield
    finally:
        try:
            proxy_service = injector.get(IProxyService)
            proxy_service.stop()
        except Exception:  # pragma: no cover - apenas tentativa de limpeza
            pass
        app.state.sessions.clear()


app = FastAPI(
    title="Raxy API Gateway",
    description="Monolito modular que expõe os serviços principais da biblioteca raxy.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


# Rotas raiz --------------------------------------------------------------

@app.get("/")
def healthcheck() -> dict[str, str]:
    return {"status": "Raxy API Gateway está funcionando!"}


# Registro dos routers ----------------------------------------------------

PREFIX = "/api/v1"

app.include_router(profile_router, prefix=PREFIX)
app.include_router(accounts_router, prefix=PREFIX)
app.include_router(auth_router, prefix=PREFIX)
app.include_router(proxy_router, prefix=PREFIX)
app.include_router(rewards_router, prefix=PREFIX)
app.include_router(suggestion_router, prefix=PREFIX)
app.include_router(logging_router, prefix=PREFIX)
app.include_router(executor_router, prefix=PREFIX)

__all__ = ["app"]


# 2. Adicione este bloco no final do arquivo
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )