"""Schemas relacionados a proxies."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class ProxySourcesRequest(BaseModel):
    """Requisição para configurar fontes de proxy."""
    
    sources: List[str] = Field(..., description="Lista de fontes de proxy")


class ProxyAddRequest(BaseModel):
    """Requisição para adicionar proxies."""
    
    proxies: List[str] = Field(..., description="Lista de proxies para adicionar")


class ProxyStartRequest(BaseModel):
    """Requisição para iniciar serviço de proxy."""
    
    threads: Optional[int] = Field(None, description="Número de threads")
    amounts: Optional[int] = Field(None, description="Quantidade de proxies")
    country: Optional[str] = Field(None, description="Código do país")
    auto_test: bool = Field(True, description="Testar proxies automaticamente")
    wait: bool = Field(False, description="Aguardar conclusão")


class ProxyTestRequest(BaseModel):
    """Requisição para testar proxies."""
    
    threads: Optional[int] = Field(None, description="Número de threads para teste")
    country: Optional[str] = Field(None, description="Código do país para filtro")
    verbose: Optional[bool] = Field(None, description="Modo verboso")
    force_refresh: bool = Field(False, description="Forçar atualização")
    timeout: float = Field(10.0, description="Timeout em segundos")
    force: bool = Field(False, description="Forçar teste mesmo se já testado")


class ProxyRotateRequest(BaseModel):
    """Requisição para rotacionar proxy."""
    
    bridge_id: int = Field(..., description="ID da bridge para rotacionar")


class ProxyOperationResponse(BaseModel):
    """Resposta de operação de proxy."""
    
    status: str
    detail: Optional[str] = None
