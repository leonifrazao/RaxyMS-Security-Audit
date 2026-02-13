from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, Generator, ContextManager
from pathlib import Path
import subprocess

from raxy.models.proxy import Outbound


class IProxyProcessManager(ABC):
    @abstractmethod
    def which_xray(self) -> str:
        """Descobre o binário do Xray/V2Ray."""
        pass

    @abstractmethod
    def find_available_port(self) -> int:
        """Encontra uma porta TCP disponível."""
        pass

    @abstractmethod
    def release_port(self, port: Optional[int]) -> None:
        """Libera uma porta alocada."""
        pass

    @abstractmethod
    def terminate_process(self, proc: Optional[subprocess.Popen], *, wait_timeout: float = 3.0) -> None:
        """Finaliza um processo."""
        pass

    @abstractmethod
    def safe_remove_dir(self, path: Optional[Path]) -> None:
        """Remove diretório sem erro."""
        pass

    @abstractmethod
    def make_xray_config_http_inbound(self, port: int, outbound: Outbound) -> Dict[str, Any]:
        """Cria config do Xray."""
        pass

    @abstractmethod
    def launch_bridge_with_diagnostics(
        self, xray_bin: str, cfg: Dict[str, Any], name: str
    ) -> Tuple[subprocess.Popen, Path]:
        """Lança processo bridge."""
        pass

    @abstractmethod
    def temporary_bridge(
        self,
        outbound: Outbound,
        *,
        tag_prefix: str = "temp",
    ) -> ContextManager[Tuple[int, subprocess.Popen]]:
        """Context manager para bridge temporária."""
        pass


class IProxyNetworkManager(ABC):
    @abstractmethod
    def read_source_text(self, source: str) -> str:
        """Lê texto de arquivo ou URL."""
        pass

    @abstractmethod
    def outbound_host_port(self, outbound: Outbound) -> Tuple[str, int]:
        """Extrai host/port do outbound."""
        pass

    @abstractmethod
    def test_outbound(self, raw_uri: str, outbound: Outbound, timeout: float = 10.0) -> Dict[str, Any]:
        """Testa conectividade real."""
        pass

    @abstractmethod
    def test_proxy_functionality(
        self, 
        raw_uri: str, 
        outbound: Outbound,
        timeout: float = 10.0,
        test_url: str = "http://httpbin.org/ip"
    ) -> Dict[str, Any]:
        """Teste funcional via requests."""
        pass
