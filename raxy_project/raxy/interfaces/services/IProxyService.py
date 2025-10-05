"""Contrato para gerenciamento de proxys via Xray/V2Ray."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable, List, Optional, Dict


class IProxyService(ABC):
    """Define operacoes publicas para manipulacao de proxys."""

    @property
    @abstractmethod
    def entries(self) -> List[Dict[str, Any]]:
        """Retorna os registros carregados ou decorrentes dos últimos testes."""
        raise NotImplementedError

    @property
    @abstractmethod
    def parse_errors(self) -> List[str]:
        """Lista de linhas ignoradas ao interpretar os links informados."""
        raise NotImplementedError

    @abstractmethod
    def add_proxies(self, proxies: Iterable[str]) -> int:
        """Adiciona proxys a partir de URIs completos (ss, vmess, vless, trojan)."""
        raise NotImplementedError

    @abstractmethod
    def add_sources(self, sources: Iterable[str]) -> int:
        """Carrega proxys de arquivos locais ou URLs linha a linha."""
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
        find_first: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Testa as proxies carregadas usando rota real para medir ping."""
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
        find_first: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Cria pontes HTTP locais para as proxys aprovadas opcionalmente testando antes."""
        raise NotImplementedError

    @abstractmethod
    def wait(self) -> None:
        """Bloqueia até que todas as pontes terminem ou ``stop`` seja chamado."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Finaliza processos Xray ativos e limpa arquivos temporários."""
        raise NotImplementedError

    @abstractmethod
    def get_http_proxy(self) -> List[Dict[str, Any]]:
        """Retorna ID, URL local e URI de cada ponte em execução."""
        raise NotImplementedError

    @abstractmethod
    def rotate_proxy(self, bridge_id: int) -> bool:
        """Troca a proxy de uma ponte em execução por outra proxy aleatória e funcional."""
        raise NotImplementedError