"""Utilitário para inspecionar respostas de rede emitidas pelo botasaurus."""

import re
from botasaurus.browser import Driver, cdp


class NetWork:
    def __init__(self, driver=None):
        self.respostas = []
        self.driver = None
        self._handler_registrado = False
        self._regex_cache = {}

        if driver:
            self.inicializar(driver)

    def inicializar(self, driver: Driver):
        if self.driver is not driver:
            self._handler_registrado = False

        self.driver = driver
        self.respostas.clear()

        if not self._handler_registrado:
            self.driver.after_response_received(self.registrar_resposta)
            self._handler_registrado = True

    def get_status(self, url_pattern=None):
        if not self.respostas:
            return None

        for resp in reversed(self.respostas):
            url = resp["url"]

            # nenhum filtro -> última resposta
            if url_pattern is None:
                return resp["status"]

            # regex pronta
            if isinstance(url_pattern, re.Pattern):
                if url_pattern.search(url):
                    return resp["status"]
                continue

            # substring direta
            if isinstance(url_pattern, str) and url_pattern in url:
                return resp["status"]

            # string interpretada como regex
            try:
                regex = self._regex_cache.get(url_pattern)
                if regex is None:
                    regex = re.compile(url_pattern)
                    self._regex_cache[url_pattern] = regex
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
