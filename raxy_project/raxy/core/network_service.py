"""Utilitário para inspecionar respostas de rede emitidas pelo botasaurus."""

from __future__ import annotations
import re
from typing import Optional
from botasaurus.browser import Driver, cdp
from raxy.core.exceptions import BrowserException, wrap_exception

class NetWork:
    """Captura e permite a inspeção de respostas de rede de uma instância de Driver com tratamento de erros."""
    def __init__(self, driver: Optional[Driver] = None):
        self.respostas: list[dict] = []
        self.driver: Optional[Driver] = None
        self._handler_registrado = False
        self._regex_cache: dict[str, re.Pattern] = {}

        if driver:
            try:
                self.inicializar(driver)
            except Exception as e:
                # Log mas não falha na inicialização
                pass

    def inicializar(self, driver: Driver) -> None:
        """Inicializa o capturador de rede com um driver específico."""
        try:
            if self.driver is not driver:
                self._handler_registrado = False

            self.driver = driver
            self.respostas.clear()

            if not self._handler_registrado and self.driver:
                self.driver.after_response_received(self.registrar_resposta)
                self._handler_registrado = True
        except Exception as e:
            raise wrap_exception(
                e, BrowserException,
                "Erro ao inicializar capturador de rede"
            )

    def get_status(self, url_pattern: Optional[str | re.Pattern] = None) -> Optional[int]:
        """Obtém o status HTTP com tratamento seguro de erros."""
        try:
            if not self.respostas:
                return None

            for resp in reversed(self.respostas):
                if not isinstance(resp, dict):
                    continue
                
                url = resp.get("url")
                if not url:
                    continue

                if url_pattern is None:
                    return resp.get("status")

                if isinstance(url_pattern, re.Pattern):
                    try:
                        if url_pattern.search(url):
                            return resp.get("status")
                    except Exception:
                        continue
                    continue

                if isinstance(url_pattern, str) and url_pattern in url:
                    return resp.get("status")

                try:
                    regex = self._regex_cache.get(url_pattern)
                    if regex is None:
                        regex = re.compile(str(url_pattern))
                        self._regex_cache[str(url_pattern)] = regex
                    if regex.search(url):
                        return resp.get("status")
                except (re.error, TypeError):
                    continue
        except Exception:
            # Retorna None em caso de qualquer erro
            return None
        return None

    def limpar_respostas(self) -> None:
        """Limpa todas as respostas capturadas."""
        try:
            self.respostas.clear()
        except Exception:
            # Recria lista se houver erro
            self.respostas = []

    def registrar_resposta(self, request_id, response: cdp.network.Response, event: cdp.network.ResponseReceived) -> None:
        """Registra uma resposta de rede capturada."""
        try:
            self.respostas.append(
                {
                    "url": response.url if hasattr(response, 'url') else None,
                    "status": response.status if hasattr(response, 'status') else None,
                    "timestamp": event.timestamp if hasattr(event, 'timestamp') else None,
                    "type": event.type_ if hasattr(event, 'type_') else None,
                    "headers": response.headers if hasattr(response, 'headers') else {},
                }
            )
        except Exception:
            # Silenciosamente ignora erros ao registrar respostas
            pass

__all__ = ["NetWork"]