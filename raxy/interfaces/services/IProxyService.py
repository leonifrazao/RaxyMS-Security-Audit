"""Contrato para gerenciamento de proxys via Xray/V2Ray."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any


class IProxyService(ABC):
    """Define operacoes publicas para manipulacao de proxys."""

    @property
    @abstractmethod
    def entries(self) -> list[dict[str, Any]]:
        """Retorna os registros resultantes dos ultimos testes."""
        raise NotImplementedError

    @property
    @abstractmethod
    def parse_errors(self) -> list[str]:
        """Lista as linhas rejeitadas ao interpretar as fontes de proxy."""
        raise NotImplementedError

    @abstractmethod
    def add_proxies(self, proxies: Iterable[str]) -> int:
        """Adiciona proxys a partir de URIs completos."""
        raise NotImplementedError

    @abstractmethod
    def add_sources(self, sources: Iterable[str]) -> int:
        """Carrega proxys a partir de arquivos locais ou URLs."""
        raise NotImplementedError

    @abstractmethod
    def test(
        self,
        *,
        threads: int | None = None,
        country: str | None = None,
        verbose: bool | None = None,
        force_refresh: bool = False,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        """Executa verificacoes de conectividade e retorna os registros atualizados."""
        raise NotImplementedError

    @abstractmethod
    def start(
        self,
        *,
        threads: int | None = None,
        amounts: int | None = None,
        country: str | None = None,
        auto_test: bool = True,
        wait: bool = False,
    ) -> list[str]:
        """Inicia pontes HTTP locais retornando as URLs prontas para uso."""
        raise NotImplementedError

    @abstractmethod
    def wait(self) -> None:
        """Bloqueia ate que todas as pontes encerrem ou sejam interrompidas."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Finaliza processos ativos e limpa recursos temporarios."""
        raise NotImplementedError

    @abstractmethod
    def get_http_proxy(self) -> list[str]:
        """Retorna URLs HTTP locais atualmente disponiveis."""
        raise NotImplementedError
