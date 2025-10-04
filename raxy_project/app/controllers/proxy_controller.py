"""Endpoints que expõem operações do serviço de proxys."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_proxy_service
from ..schemas import (
    ProxyAddRequest,
    ProxyOperationResponse,
    ProxyRotateRequest,
    ProxySourcesRequest,
    ProxyStartRequest,
    ProxyTestRequest,
)
from raxy.interfaces.services import IProxyService

router = APIRouter(prefix="/proxy", tags=["Proxy"])


@router.post("/sources", response_model=ProxyOperationResponse)
def add_sources(
    payload: ProxySourcesRequest,
    proxy_service: IProxyService = Depends(get_proxy_service),
) -> ProxyOperationResponse:
    quantidade = proxy_service.add_sources(payload.sources)
    return ProxyOperationResponse(status="sources_loaded", detail=f"{quantidade} fontes processadas")


@router.post("/proxies", response_model=ProxyOperationResponse)
def add_proxies(
    payload: ProxyAddRequest,
    proxy_service: IProxyService = Depends(get_proxy_service),
) -> ProxyOperationResponse:
    quantidade = proxy_service.add_proxies(payload.proxies)
    return ProxyOperationResponse(status="proxies_loaded", detail=f"{quantidade} proxies adicionadas")


@router.post("/test")
def test_proxies(
    payload: ProxyTestRequest,
    proxy_service: IProxyService = Depends(get_proxy_service),
):
    resultados = proxy_service.test(
        threads=payload.threads,
        country=payload.country,
        verbose=payload.verbose,
        force_refresh=payload.force_refresh,
        timeout=payload.timeout,
        force=payload.force,
    )
    return {"status": "tested", "total": len(resultados), "entries": resultados}


@router.post("/start")
def start_proxies(
    payload: ProxyStartRequest,
    proxy_service: IProxyService = Depends(get_proxy_service),
):
    bridges = proxy_service.start(
        threads=payload.threads,
        amounts=payload.amounts,
        country=payload.country,
        auto_test=payload.auto_test,
        wait=payload.wait,
    )
    return {"status": "started", "bridges": bridges}


@router.post("/stop", response_model=ProxyOperationResponse)
def stop_proxies(proxy_service: IProxyService = Depends(get_proxy_service)) -> ProxyOperationResponse:
    proxy_service.stop()
    return ProxyOperationResponse(status="stopped")


@router.get("/entries")
def list_entries(proxy_service: IProxyService = Depends(get_proxy_service)):
    return {"entries": proxy_service.entries, "parse_errors": proxy_service.parse_errors}


@router.get("/bridges")
def list_bridges(proxy_service: IProxyService = Depends(get_proxy_service)):
    return {"bridges": proxy_service.get_http_proxy()}


@router.post("/rotate", response_model=ProxyOperationResponse)
def rotate_proxy(
    payload: ProxyRotateRequest,
    proxy_service: IProxyService = Depends(get_proxy_service),
) -> ProxyOperationResponse:
    if proxy_service.rotate_proxy(payload.bridge_id):
        return ProxyOperationResponse(status="rotated")
    raise HTTPException(status_code=404, detail="Bridge não encontrada para rotação")
