"""Utilitário para inspecionar respostas de rede emitidas pelo botasaurus."""

from __future__ import annotations
import re
from botasaurus.browser import Driver, cdp

class NetWork:
    """Captura e permite a inspeção de respostas de rede de uma instância de Driver."""
    def __init__(self, driver: Driver | None = None):
        self.respostas: list[dict] = []
        self.driver: Driver | None = None
        self._handler_registrado = False
        self._regex_cache: dict[str, re.Pattern] = {}

        if driver:
            self.inicializar(driver)

    def inicializar(self, driver: Driver):
        if self.driver is not driver:
            self._handler_registrado = False

        self.driver = driver
        self.respostas.clear()

        if not self._handler_registrado and self.driver:
            self.driver.after_response_received(self.registrar_resposta)
            self._handler_registrado = True

    def get_status(self, url_pattern: str | re.Pattern | None = None) -> int | None:
        if not self.respostas:
            return None

        for resp in reversed(self.respostas):
            url = resp["url"]

            if url_pattern is None:
                return resp["status"]

            if isinstance(url_pattern, re.Pattern):
                if url_pattern.search(url):
                    return resp["status"]
                continue

            if isinstance(url_pattern, str) and url_pattern in url:
                return resp["status"]

            try:
                regex = self._regex_cache.get(url_pattern)
                if regex is None:
                    regex = re.compile(str(url_pattern))
                    self._regex_cache[str(url_pattern)] = regex
                if regex.search(url):
                    return resp["status"]
            except re.error:
                return None
        return None

    def limpar_respostas(self):
        self.respostas.clear()

    def registrar_resposta(self, request_id, response: cdp.network.Response, event: cdp.network.ResponseReceived):
        self.respostas.append(
            {
                "url": response.url,
                "status": response.status,
                "timestamp": event.timestamp,
                "type": event.type_,
                "headers": response.headers,
            }
        )

__all__ = ["NetWork"]