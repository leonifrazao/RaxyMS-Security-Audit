from botasaurus.browser import browser, Driver, cdp
from typing import Dict, List, Optional
import re

class NetWork:
    def __init__(self):
        self.respostas: List[Dict] = []
        self.driver: Optional[Driver] = None
        self._handler_registrado = False
    
    def inicializar(self, driver: Driver):
        """Inicializa o monitoramento de rede para um driver específico."""
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
        """Handler para capturar todas as respostas de rede."""
        self.respostas.append({
            "url": response.url,
            "status": response.status,
            "timestamp": event.timestamp,
            "type": event.type_,
            "headers": response.headers
        })
    
    def get_status(self, url_pattern: str = None) -> Optional[int]:
        """
        Retorna o status code da URL mais recente que corresponde ao padrão.
        Se url_pattern for None, retorna o status da última resposta.
        """
        if not self.respostas:
            return None
        
        if url_pattern is None:
            # Retorna o status da última resposta
            return self.respostas[-1]["status"]
        
        # Filtra respostas que correspondem ao padrão
        respostas_filtradas = []
        for resp in self.respostas:
            if url_pattern in resp["url"] or re.search(url_pattern, resp["url"]):
                respostas_filtradas.append(resp)
        
        if respostas_filtradas:
            # Retorna o status da resposta mais recente que corresponde
            return respostas_filtradas[-1]["status"]
        
        return None
    
    def get_ultima_resposta(self, url_pattern: str = None) -> Optional[Dict]:
        """
        Retorna a última resposta completa (url e status) que corresponde ao padrão.
        """
        if not self.respostas:
            return None
        
        if url_pattern is None:
            return {
                "url": self.respostas[-1]["url"],
                "status": self.respostas[-1]["status"]
            }
        
        # Filtra respostas que correspondem ao padrão
        for resp in reversed(self.respostas):
            if url_pattern in resp["url"] or re.search(url_pattern, resp["url"]):
                return {
                    "url": resp["url"],
                    "status": resp["status"]
                }
        
        return None
    
    def limpar_respostas(self):
        """Limpa o histórico de respostas capturadas."""
        self.respostas = []
    
    def get_todas_respostas(self) -> List[Dict]:
        """Retorna todas as respostas capturadas."""
        return self.respostas