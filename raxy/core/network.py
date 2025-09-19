from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Pattern

from botasaurus.browser import Driver, cdp

class NetWork:
    """Utilitário para inspecionar respostas de rede emitidas pelo botasaurus."""

    def __init__(self, driver: Optional[Driver] = None):
        """Inicializa estrutura vazia para capturar respostas de rede."""

        self.respostas: List[Dict[str, Any]] = []
        self.driver: Optional[Driver] = None
        self._handler_registrado = False
        self._regex_cache: Dict[str, Pattern[str]] = {}

        if driver is not None:
            self.inicializar(driver)

    def inicializar(self, driver: Driver):
        """Inicializa o monitoramento de rede para um driver específico.

        Args:
            driver: Instância do botasaurus monitorada.
        """
        driver_anterior = self.driver
        if driver_anterior is not driver:
            self._handler_registrado = False

        self.driver = driver
        self.respostas = []

        if not self._handler_registrado:
            self.driver.after_response_received(self._response_handler)
            self._handler_registrado = True

    def _response_handler(
        self,
        request_id: str,
        response: cdp.network.Response,
        event: cdp.network.ResponseReceived,
    ):
        """Handler interno registrado no CDP para capturar respostas."""
        self.respostas.append(
            {
                "url": response.url,
                "status": response.status,
                "timestamp": event.timestamp,
                "type": event.type_,
                "headers": response.headers,
            }
        )

    def get_status(self, url_pattern: str | Pattern[str] | None = None) -> Optional[int]:
        """Obtém o status HTTP mais recente cuja URL combina com ``url_pattern``.

        Args:
            url_pattern: Texto ou regex a ser testada contra as URLs capturadas.

        Returns:
            Código de status ou ``None`` quando não há correspondências.
        """
        if not self.respostas:
            return None

        if url_pattern is None:
            return self.respostas[-1]["status"]

        for resp in reversed(self.respostas):
            if self._combina(resp["url"], url_pattern):
                return resp["status"]
        return None


    def limpar_respostas(self):
        """Limpa o histórico de respostas capturadas."""
        self.respostas.clear()

    def _combina(self, url: str, padrao: str | Pattern[str]) -> bool:
        """Verifica se ``url`` satisfaz o padrão informado (substring ou regex)."""

        if isinstance(padrao, re.Pattern):
            try:
                return bool(padrao.search(url))
            except re.error:
                return False

        if padrao in url:
            return True

        try:
            regex = self._regex_cache.get(padrao)
            if regex is None:
                regex = re.compile(padrao)
                self._regex_cache[padrao] = regex
            return bool(regex.search(url))
        except re.error:
            return False
