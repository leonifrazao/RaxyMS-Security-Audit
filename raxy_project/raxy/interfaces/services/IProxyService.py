from __future__ import annotations
from typing import List, Dict, Optional, Iterable, Any, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from raxy.domain.proxy import ProxyItem


class IProxyService(ABC):
    """Interface para gerenciamento de proxies (v2ray/xray)."""

    @abstractmethod
    def add_sources(self, sources: Iterable[str]) -> int:
        """Adiciona proxies a partir de fontes (linhas de URIs)."""
        raise NotImplementedError

    @abstractmethod
    def add_proxies(self, proxies: Iterable[str]) -> int:
        """Adiciona proxies diretamente (URIs)."""
        raise NotImplementedError

    @abstractmethod
    def test(
        self, 
        *, 
        threads: Optional[int] = 1, 
        country: Optional[str] = None,
        verbose: Optional[bool] = None,
        timeout: float = 10.0,
        force: bool = False,
        find_first: Optional[int] = None
    ) -> List["ProxyItem"]:
        """Testa proxies carregados e retorna resultados."""
        raise NotImplementedError

    @abstractmethod
    def start(
        self, 
        *, 
        threads: Optional[int] = None,
        amounts: Optional[int] = None, 
        country: Optional[str] = None,
        auto_test: bool = True,
        wait: bool = False,
        find_first: Optional[int] = None
    ) -> List["ProxyItem"]:
        """Inicia pontes HTTP locais e retorna lista de proxies ativos."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Encerra todas as pontes ativas."""
        raise NotImplementedError

    @abstractmethod
    def get_http_proxy(self) -> List[Dict[str, Any]]:
        """Lista proxies HTTP ativos (id, url, uri)."""
        raise NotImplementedError

    @abstractmethod
    def rotate_proxy(self, bridge_id: int) -> bool:
        """Troca a proxy de uma ponte em execução por outra proxy aleatória e funcional."""
        raise NotImplementedError

    @abstractmethod
    def wait(self) -> None:
        """Bloqueia até que todas as pontes terminem ou ``stop`` seja chamado."""
        raise NotImplementedError
