"""Endpoints que expõem operações do serviço de proxys."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_proxy_service
from app.schemas import (
    ProxyAddRequest,
    ProxyOperationResponse,
    ProxyRotateRequest,
    ProxySourcesRequest,
    ProxyStartRequest,
    ProxyTestRequest,
)
from app.core import BaseController
from raxy.interfaces.services import IProxyService


class ProxyController(BaseController):
    """Controller para gerenciamento de proxies."""
    
    def __init__(self):
        super().__init__()
        self.router = APIRouter(prefix="/proxy", tags=["Proxy"])
        self._register_routes()
    
    def _register_routes(self):
        """Registra as rotas do controller."""
        routes = [
            ("/sources", self.add_sources, ["POST"], ProxyOperationResponse),
            ("/proxies", self.add_proxies, ["POST"], ProxyOperationResponse),
            ("/test", self.test_proxies, ["POST"], None),
            ("/start", self.start_proxies, ["POST"], None),
            ("/stop", self.stop_proxies, ["POST"], ProxyOperationResponse),
            ("/entries", self.list_entries, ["GET"], None),
            ("/bridges", self.list_bridges, ["GET"], None),
            ("/rotate", self.rotate_proxy, ["POST"], ProxyOperationResponse),
        ]
        
        for path, endpoint, methods, response_model in routes:
            kwargs = {"methods": methods}
            if response_model:
                kwargs["response_model"] = response_model
            self.router.add_api_route(path, endpoint, **kwargs)
    
    def add_sources(
        self,
        payload: ProxySourcesRequest,
        proxy_service: IProxyService = Depends(get_proxy_service),
    ) -> ProxyOperationResponse:
        """Adiciona fontes de proxy ao serviço."""
        self.log_request("add_sources", {"count": len(payload.sources)})
        
        try:
            quantidade = proxy_service.add_sources(payload.sources)
            response = ProxyOperationResponse(
                status="sources_loaded",
                detail=f"{quantidade} fontes processadas"
            )
            self.log_response("add_sources", {"processed": quantidade})
            return response
        except Exception as e:
            self.handle_service_error(e, "add_sources")
    
    def add_proxies(
        self,
        payload: ProxyAddRequest,
        proxy_service: IProxyService = Depends(get_proxy_service),
    ) -> ProxyOperationResponse:
        """Adiciona proxies ao serviço."""
        self.log_request("add_proxies", {"count": len(payload.proxies)})
        
        try:
            quantidade = proxy_service.add_proxies(payload.proxies)
            response = ProxyOperationResponse(
                status="proxies_loaded",
                detail=f"{quantidade} proxies adicionadas"
            )
            self.log_response("add_proxies", {"added": quantidade})
            return response
        except Exception as e:
            self.handle_service_error(e, "add_proxies")
    
    def test_proxies(
        self,
        payload: ProxyTestRequest,
        proxy_service: IProxyService = Depends(get_proxy_service),
    ):
        """Testa proxies disponíveis."""
        self.log_request("test_proxies", {
            "threads": payload.threads,
            "country": payload.country
        })
        
        try:
            resultados = proxy_service.test(
                threads=payload.threads,
                country=payload.country,
                verbose=payload.verbose,
                force_refresh=payload.force_refresh,
                timeout=payload.timeout,
                force=payload.force,
            )
            response = {
                "status": "tested",
                "total": len(resultados),
                "entries": resultados
            }
            self.log_response("test_proxies", {"total": len(resultados)})
            return response
        except Exception as e:
            self.handle_service_error(e, "test_proxies")
    
    def start_proxies(
        self,
        payload: ProxyStartRequest,
        proxy_service: IProxyService = Depends(get_proxy_service),
    ):
        """Inicia serviço de proxies."""
        self.log_request("start_proxies", {
            "threads": payload.threads,
            "amounts": payload.amounts
        })
        
        try:
            bridges = proxy_service.start(
                threads=payload.threads,
                amounts=payload.amounts,
                country=payload.country,
                auto_test=payload.auto_test,
                wait=payload.wait,
            )
            response = {"status": "started", "bridges": bridges}
            self.log_response("start_proxies", {"bridges_count": len(bridges)})
            return response
        except Exception as e:
            self.handle_service_error(e, "start_proxies")
    
    def stop_proxies(
        self,
        proxy_service: IProxyService = Depends(get_proxy_service)
    ) -> ProxyOperationResponse:
        """Para o serviço de proxies."""
        self.log_request("stop_proxies")
        
        try:
            proxy_service.stop()
            response = ProxyOperationResponse(status="stopped")
            self.log_response("stop_proxies", {"status": "stopped"})
            return response
        except Exception as e:
            self.handle_service_error(e, "stop_proxies")
    
    def list_entries(
        self,
        proxy_service: IProxyService = Depends(get_proxy_service)
    ):
        """Lista entradas de proxy disponíveis."""
        self.log_request("list_entries")
        
        try:
            response = {
                "entries": proxy_service.entries,
                "parse_errors": proxy_service.parse_errors
            }
            self.log_response("list_entries", {
                "entries_count": len(proxy_service.entries)
            })
            return response
        except Exception as e:
            self.handle_service_error(e, "list_entries")
    
    def list_bridges(
        self,
        proxy_service: IProxyService = Depends(get_proxy_service)
    ):
        """Lista bridges de proxy ativas."""
        self.log_request("list_bridges")
        
        try:
            bridges = proxy_service.get_http_proxy()
            response = {"bridges": bridges}
            self.log_response("list_bridges", {
                "bridges_count": len(bridges) if bridges else 0
            })
            return response
        except Exception as e:
            self.handle_service_error(e, "list_bridges")
    
    def rotate_proxy(
        self,
        payload: ProxyRotateRequest,
        proxy_service: IProxyService = Depends(get_proxy_service),
    ) -> ProxyOperationResponse:
        """Rotaciona proxy específico."""
        self.log_request("rotate_proxy", {"bridge_id": payload.bridge_id})
        
        try:
            if proxy_service.rotate_proxy(payload.bridge_id):
                response = ProxyOperationResponse(status="rotated")
                self.log_response("rotate_proxy", {"bridge_id": payload.bridge_id})
                return response
            raise HTTPException(status_code=404, detail="Bridge não encontrada para rotação")
        except HTTPException:
            raise
        except Exception as e:
            self.handle_service_error(e, "rotate_proxy")


# Cria instância do controller e exporta o router
controller = ProxyController()
router = controller.router

__all__ = ["router", "ProxyController"]
