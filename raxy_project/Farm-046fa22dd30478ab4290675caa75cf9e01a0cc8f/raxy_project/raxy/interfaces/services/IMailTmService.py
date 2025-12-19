from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

class IMailTmService(ABC):
    
    @abstractmethod
    def get_domains(self) -> list[str]:
        """Retorna a lista de domínios disponíveis no Mail.tm."""
    
    @abstractmethod
    def create_account(self, address, password) -> dict:
        """
        Cria uma nova conta e obtém o token de autenticação.
        """
        pass
    
    @abstractmethod
    def get_token(self, address, password):
        """
        Obtém um token JWT para uma conta existente.
        """
        pass
    
    @abstractmethod
    def get_me(self):
        """
        Recupera os detalhes da conta associada ao token atual.
        """
        pass
    
    @abstractmethod
    def delete_account(self):
        """
        Exclui a conta associada ao token atual.
        """
        pass
    
    @abstractmethod
    def get_messages(self, page=1):
        """
        Recupera uma coleção de mensagens para a conta autenticada.
        """
        pass
    
    @abstractmethod
    def get_message(self, message_id):
        """
        Recupera os detalhes de uma mensagem específica pelo seu ID.
        """
        pass
    
    @abstractmethod
    def mark_message_as_seen(self, message_id, seen=True):
        """
        Atualiza o status de 'visto' de uma mensagem.
        """
        pass
    
    @abstractmethod
    def create_random_account(self, password=None, max_attempts=20, delay=1) -> dict:
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
    def wait_for_message(self, timeout=60, interval=5, filter_func=None):
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
    def filter_messages(self, subject_contains=None, from_address=None):
        """
        Filtra mensagens já recebidas.
        """
        pass
    