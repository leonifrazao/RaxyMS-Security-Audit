"""Endpoints para proxies."""

from __future__ import annotations
from typing import Optional
from fastapi import APIRouter

from raxy.infrastructure.logging import get_logger
from raxy.infrastructure.config.config import get_config
from raxy.adapters.http.schemas import (
    ProxyResponse,
    ProxiesResponse,
    ProxyTestRequest,
    ProxyTestResponse,
    ProxyRotateRequest,
)

router = APIRouter(prefix="/proxy", tags=["Proxy"])
logger = get_logger()


def _get_proxy_manager():
    from raxy.infrastructure.manager import ProxyManager
    config = get_config()
    return ProxyManager(sources=config.proxy.sources, use_console=False)


@router.get("", response_model=ProxiesResponse)
def list_proxies() -> ProxiesResponse:
    """Lista os proxies disponíveis."""
    proxy_service = _get_proxy_manager()
    proxies = proxy_service.get_http_proxy() or []
    
    items = [
        ProxyResponse(
            id=str(p.get("id", i)),
            url=p.get("http", p.get("url", str(p))),
            status="active" if p.get("http") else "available"
        )
        for i, p in enumerate(proxies) if isinstance(p, dict)
    ]
    return ProxiesResponse(proxies=items)


@router.get("/current")
def get_current_proxy():
    """Retorna o proxy HTTP ativo."""
    proxy_service = _get_proxy_manager()
    current = proxy_service.get_http_proxy()
    
    if current:
        return {"proxy": current, "status": "active"}
    return {"proxy": None, "status": "none"}


@router.post("/test", response_model=ProxyTestResponse)
def test_proxies(request: ProxyTestRequest) -> ProxyTestResponse:
    """Testa os proxies."""
    proxy_service = _get_proxy_manager()
    
    proxy_service.test(
        threads=request.threads or 10,
        country=request.country,
        timeout=request.timeout or 10.0,
        force=request.force or False,
        find_first=request.find_first,
        verbose=False,
    )
    
    working = proxy_service.get_proxies() or []
    return ProxyTestResponse(
        tested=len(working),
        working=len(working),
        message=f"Teste concluído: {len(working)} proxies funcionando"
    )


@router.post("/start")
def start_proxies(
    amounts: Optional[int] = None,
    country: Optional[str] = None,
):
    """Inicia as pontes de proxy."""
    proxy_service = _get_proxy_manager()
    proxy_service.start(amounts=amounts, country=country, auto_test=True, wait=False)
    return {"status": "started", "message": "Pontes de proxy iniciadas"}


@router.post("/stop")
def stop_proxies():
    """Para as pontes de proxy."""
    proxy_service = _get_proxy_manager()
    proxy_service.stop()
    return {"status": "stopped", "message": "Pontes de proxy paradas"}


@router.post("/rotate")
def rotate_proxy(request: ProxyRotateRequest):
    """Rotaciona o proxy de uma ponte."""
    proxy_service = _get_proxy_manager()
    success = proxy_service.rotate_proxy(request.bridge_id)
    
    if success:
        return {"status": "rotated", "bridge_id": request.bridge_id}
    return {"status": "failed", "message": "Falha ao rotacionar proxy"}


__all__ = ["router"]
