# raxy_project/app/main.py

"""Ponto de entrada FastAPI que atua como API Gateway para a biblioteca raxy."""

from __future__ import annotations
import sys
import os
# Adiciona o diretório pai ao path para encontrar o módulo raxy
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carrega variáveis de ambiente do arquivo .env
from dotenv import load_dotenv
load_dotenv()

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from raxy.container import get_container

from app.controllers import (
    accounts_router,
    auth_router,
    executor_router,
    logging_router,
    proxy_router,
    rewards_router,
    suggestion_router,
    flyout_router,
    mailtm_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia recursos globais ao iniciar/encerrar a API."""

    container = get_container()
    app.state.container = container
    app.state.sessions = {}
    
    # Initialize Redis connection for RQ
    config = container.config()
    if config.events.enabled:
        from redis import Redis
        from rq import Queue
        
        app.state.redis_conn = Redis(
            host=config.events.host,
            port=config.events.port,
            db=config.events.db,
            password=config.events.password,
        )
        app.state.task_queue = Queue(connection=app.state.redis_conn)
        print(f"✅ Connected to Redis at {config.events.host}:{config.events.port}")
    else:
        app.state.redis_conn = None
        app.state.task_queue = None
        print("⚠️ Redis is disabled in config. Background jobs will not work.")
        
    try:
        yield
    finally:
        if getattr(app.state, "redis_conn", None):
            app.state.redis_conn.close()
            
        try:
            proxy_service = container.proxy_service()
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

# app.include_router(profile_router, prefix=PREFIX) # Removido
app.include_router(accounts_router, prefix=PREFIX)
app.include_router(auth_router, prefix=PREFIX)
app.include_router(proxy_router, prefix=PREFIX)
app.include_router(rewards_router, prefix=PREFIX)
app.include_router(suggestion_router, prefix=PREFIX)
app.include_router(logging_router, prefix=PREFIX)
app.include_router(executor_router, prefix=PREFIX)
app.include_router(flyout_router, prefix=PREFIX)
app.include_router(mailtm_router, prefix=PREFIX)

__all__ = ["app"]


# Adicione este bloco no final do arquivo para torná-lo executável
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )