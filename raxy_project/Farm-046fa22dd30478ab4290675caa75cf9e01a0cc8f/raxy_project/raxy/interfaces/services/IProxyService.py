from __future__ import annotations
from typing import List, Dict, Optional
from abc import ABC, abstractmethod


class IProxyService(ABC):
    """Interface para gerenciamento de proxies (v2ray/xray)."""

    @abstractmethod
    def add_sources(self, sources: List[str]) -> int:
        """Adiciona proxies a partir de fontes (linhas de URIs)."""
        raise NotImplementedError

    @abstractmethod
    def add_proxies(self, proxies: List[str]) -> int:
        """Adiciona proxies diretamente (URIs)."""
        raise NotImplementedError

    @abstractmethod
    def test(self, *, threads: Optional[int] = 1, force: bool = False, timeout: Optional[float] = None) -> List[Dict]:
        """Testa proxies carregados e retorna resultados."""
        raise NotImplementedError

    @abstractmethod
    def start(self, *, amounts: Optional[int] = None, auto_test: bool = True) -> List[Dict]:
        """Inicia pontes HTTP locais e retorna lista de proxies ativos."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Encerra todas as pontes ativas."""
        raise NotImplementedError

    @abstractmethod
    def get_http_proxy(self) -> List[Dict]:
        """Lista proxies HTTP ativos (id, url, uri)."""
        raise NotImplementedError

    @abstractmethod
    def rotate_proxy(self, bridge_id: int) -> bool:
        """Rotaciona proxy de uma ponte específica."""
        raise NotImplementedError
