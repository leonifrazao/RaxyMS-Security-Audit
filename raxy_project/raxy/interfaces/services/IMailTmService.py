from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

class IMailTmService(ABC):
    
    @abstractmethod
    def get_domains(self) -> list[str]:
        """Retorna a lista de domínios disponíveis no Mail.tm."""
    
    @abstractmethod
    def create_account(self, address: str, password: str) -> Any:
        """
        Cria uma nova conta e obtém o token de autenticação.
        """
        pass
    
    @abstractmethod
    def get_token(self, address: str, password: str) -> str:
        """
        Obtém um token JWT para uma conta existente.
        """
        pass
    
    @abstractmethod
    def get_me(self, token: str) -> Any:
        """
        Recupera os detalhes da conta associada ao token atual.
        """
        pass
    
    @abstractmethod
    def delete_account(self, session: Any) -> Any:
        """
        Exclui a conta associada ao token atual.
        """
        pass
    
    @abstractmethod
    def get_messages(self, token: str, page: int = 1) -> list[Any]:
        """
        Recupera uma coleção de mensagens para a conta autenticada.
        """
        pass
    
    @abstractmethod
    def get_message(self, token: str, message_id: str) -> Any:
        """
        Recupera os detalhes de uma mensagem específica pelo seu ID.
        """
        pass
    
    @abstractmethod
    def mark_message_as_seen(self, token: str, message_id: str, seen: bool = True) -> Any:
        """
        Atualiza o status de 'visto' de uma mensagem.
        """
        pass
    
    @abstractmethod
    def create_random_account(
        self, 
        password: str | None = None, 
        max_attempts: int = 20, 
        delay: int = 1
    ) -> Any:
        """
        Cria automaticamente uma conta com endereço aleatório.
        Tenta várias vezes até conseguir (caso o e-mail já exista).
        
        Args:
            password (str): senha opcional. Se None, gera uma senha aleatória.
            max_attempts (int): número máximo de tentativas.
            delay (int): segundos de espera entre tentativas.
        
        Returns:
            dict: dados da conta criada.
        """
        pass
    
    @abstractmethod
    def wait_for_message(
        self, 
        token: str, 
        timeout: int = 60, 
        interval: int = 5, 
        filter_func: Any = None
    ) -> Any:
        """
        Aguarda até que uma nova mensagem chegue.
        
        Args:
            timeout (int): tempo máximo de espera em segundos.
            interval (int): intervalo entre verificações.
            filter_func (callable): função opcional para filtrar mensagens.
        
        Returns:
            dict: A primeira mensagem encontrada que atende ao filtro.
        """
    
    @abstractmethod
    def filter_messages(
        self, 
        token: str, 
        subject_contains: str | None = None, 
        from_address: str | None = None
    ) -> list[Any]:
        """
        Filtra mensagens já recebidas.
        """
        pass
    