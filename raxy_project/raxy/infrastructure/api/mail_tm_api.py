"""
API refatorada para serviço de email temporário Mail.tm.

Fornece interface para criar e gerenciar emails temporários
através do serviço Mail.tm com arquitetura modular.
"""

from __future__ import annotations

import random
import string
import time
from typing import List, Optional, Dict, Any, Callable

import requests

from raxy.interfaces.services import IMailTmService, ILoggingService
from raxy.models.mailtm_data import Domain, Account, AuthenticatedSession, Message, MessageAddress
from raxy.core.exceptions import (
    MailTmAPIException,
    RequestException,
    RequestTimeoutException,
    InvalidAPIResponseException,
    wrap_exception,
)
from raxy.core.config import get_config
from .base_api import BaseAPIClient



class MailTmHelper:
    """Helper para operações do Mail.tm."""
    
    @staticmethod
    def generate_random_string(length: int) -> str:
        """
        Gera string aleatória para username/password.
        
        Args:
            length: Comprimento da string
            
        Returns:
            str: String aleatória
        """
        return ''.join(
            random.choice(string.ascii_lowercase + string.digits)
            for _ in range(length)
        )
    
    @staticmethod
    def parse_domain(domain_data: Dict[str, Any]) -> Domain:
        """
        Parse de dados de domínio.
        
        Args:
            domain_data: Dados do domínio
            
        Returns:
            Domain: Objeto de domínio
        """
        return Domain(
            id=domain_data["id"],
            domain=domain_data["domain"],
            isActive=domain_data.get("isActive", True),
            isPrivate=domain_data.get("isPrivate", False),
            createdAt=domain_data.get("createdAt"),
            updatedAt=domain_data.get("updatedAt")
        )
    
    @staticmethod
    def parse_account(account_data: Dict[str, Any]) -> Account:
        """
        Parse de dados de conta.
        
        Args:
            account_data: Dados da conta
            
        Returns:
            Account: Objeto de conta
        """
        return Account(
            id=account_data["id"],
            address=account_data["address"],
            quota=account_data.get("quota"),
            used=account_data.get("used"),
            isDisabled=account_data.get("isDisabled", False),
            isDeleted=account_data.get("isDeleted", False),
            createdAt=account_data.get("createdAt"),
            updatedAt=account_data.get("updatedAt")
        )


class MailTm(BaseAPIClient, IMailTmService):
    """
    Cliente de API para Mail.tm.
    
    Implementa a interface IMailTmService com arquitetura modular
    e tratamento robusto de erros.
    """
    
    def __init__(self, logger: Optional[ILoggingService] = None):
        """
        Inicializa o cliente Mail.tm.
        
        Args:
            logger: Serviço de logging
        """
        super().__init__(
            logger=logger,
            timeout=get_config().api.default_timeout
        )
        
        self.base_url = get_config().api.mail_tm.base_url
        
        self.helper = MailTmHelper()
        self.endpoints = get_config().api.mail_tm.endpoints
    


    def _request(self, method: str, endpoint: str, token: Optional[str] = None, **kwargs):
        """Método central para realizar requisições HTTP com tratamento robusto de erros."""
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        try:
            response = self.session.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout ao acessar {url}"
            self.logger.erro(error_msg)
            raise RequestTimeoutException(
                error_msg,
                details={"url": url, "method": method, "endpoint": endpoint}
            ) from e
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            error_msg = f"Erro na API: {status_code} - {e.response.text if e.response else 'Sem resposta'}"
            self.logger.erro(f"Erro HTTP ao acessar {url}: {error_msg}")
            raise MailTmAPIException(
                error_msg,
                details={"url": url, "method": method, "status_code": status_code}
            ) from e
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Erro de conexão ao acessar {url}"
            self.logger.erro(error_msg)
            raise RequestException(
                error_msg,
                details={"url": url, "method": method}
            ) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"Erro de requisição: {e}"
            self.logger.erro(f"Erro ao acessar {url}: {e}")
            raise wrap_exception(
                e, RequestException,
                error_msg,
                url=url, method=method
            )

    # --- Gerenciamento de Domínios ---
    
    def get_domains(self) -> List[Domain]:
        """Recupera a lista de domínios disponíveis com tratamento de erros."""
        self.logger.info("Buscando domínios disponíveis...")
        try:
            response = self._request("GET", self.endpoints["domains"])
        except MailTmAPIException:
            raise
        except Exception as e:
            raise wrap_exception(
                e, MailTmAPIException,
                "Erro ao buscar domínios"
            )
        
        if isinstance(response, dict) and "hydra:member" in response:
            try:
                return [Domain(
                    id=d['id'],
                    domain=d['domain'],
                    is_active=d['isActive'],
                    is_private=d['isPrivate'],
                    created_at=d['createdAt'],
                    updated_at=d['updatedAt']
                ) for d in response['hydra:member']]
            except (KeyError, TypeError) as e:
                raise wrap_exception(
                    e, InvalidAPIResponseException,
                    "Resposta de domínios com formato inválido"
                )
        return []

    # --- Gerenciamento de Contas e Autenticação ---

    def create_account(self, address: str, password: str) -> AuthenticatedSession:
        """Cria uma nova conta e retorna uma sessão autenticada com tratamento de erros."""
        self.logger.info(f"Criando conta para o endereço: {address}")
        payload = {"address": address, "password": password}
        
        try:
            account_data = self._request("POST", self.endpoints["accounts"], json=payload)
        except MailTmAPIException:
            raise
        except Exception as e:
            raise wrap_exception(
                e, MailTmAPIException,
                "Erro ao criar conta",
                address=address
            )
        
        try:
            account = Account(
                id=account_data['id'],
                address=account_data['address'],
                is_disabled=account_data['isDisabled'],
                is_deleted=account_data['isDeleted'],
                created_at=account_data['createdAt'],
                updated_at=account_data['updatedAt']
            )
        except (KeyError, TypeError) as e:
            raise wrap_exception(
                e, InvalidAPIResponseException,
                "Resposta de criação de conta com formato inválido",
                address=address
            )
        
        try:
            token = self.get_token(address, password)
        except MailTmAPIException:
            raise
        except Exception as e:
            raise wrap_exception(
                e, MailTmAPIException,
                "Erro ao obter token após criar conta",
                address=address
            )
        
        self.logger.info(f"Conta {account.address} criada com sucesso.")
        
        return AuthenticatedSession(account=account, token=token)

    def get_token(self, address: str, password: str) -> str:
        """Obtém um token JWT para uma conta existente com tratamento de erros."""
        self.logger.info(f"Obtendo token para {address}...")
        payload = {"address": address, "password": password}
        
        try:
            response = self._request("POST", self.endpoints["token"], json=payload)
        except MailTmAPIException:
            raise
        except Exception as e:
            raise wrap_exception(
                e, MailTmAPIException,
                "Erro ao obter token",
                address=address
            )
        
        token = response.get("token") if response else None
        if not token:
            raise MailTmAPIException(
                "Falha ao obter o token.",
                details={"address": address, "response": str(response)}
            )
        return token

    def get_me(self, token: str) -> Account:
        """Recupera os detalhes da conta associada a um token."""
        self.logger.info("Buscando detalhes da conta autenticada (/me)...")
        me_data = self._request("GET", self.endpoints["me"], token=token)
        return Account(id=me_data['id'], address=me_data['address'], is_disabled=me_data['isDisabled'], is_deleted=me_data['isDeleted'], created_at=me_data['createdAt'], updated_at=me_data['updatedAt'])


    def delete_account(self, session: AuthenticatedSession) -> None:
        """Exclui a conta associada a uma sessão autenticada."""
        account_id = session.account.id
        self.logger.info(f"Excluindo a conta {account_id}...")
        self._request("DELETE", f"{self.endpoints['accounts']}/{account_id}", token=session.token)
        self.logger.info(f"Conta {session.account.address} ({account_id}) excluída com sucesso.")

    # --- Gerenciamento de Mensagens ---
    
    def get_messages(self, token: str, page: int = 1) -> List[Message]:
        """Recupera uma coleção de mensagens para a conta associada a um token."""
        self.logger.info(f"Buscando mensagens na página {page}...")
        response = self._request("GET", f"{self.endpoints['messages']}?page={page}", token=token)
        
        messages = []
        if isinstance(response, dict) and "hydra:member" in response:
            for m in response['hydra:member']:
                from_addr = MessageAddress(address=m['from'].get('address', ''), name=m['from'].get('name', ''))
                to_addrs = [MessageAddress(address=t.get('address', ''), name=t.get('name', '')) for t in m.get('to', [])]
                messages.append(Message(id=m['id'], account_id=m['accountId'], msgid=m['msgid'], from_address=from_addr, to=to_addrs, subject=m['subject'], intro=m['intro'], seen=m['seen'], is_deleted=m['isDeleted'], has_attachments=m.get('hasAttachments', False), size=m['size'], download_url=m.get('downloadUrl', ''), created_at=m['createdAt'], updated_at=m['updatedAt']))
        return messages


    def get_message(self, token: str, message_id: str) -> Message:
        """Recupera os detalhes de uma mensagem específica pelo seu ID."""
        self.logger.info(f"Buscando detalhes da mensagem {message_id}...")
        m = self._request("GET", f"{self.endpoints['messages']}/{message_id}", token=token)
        from_addr = MessageAddress(address=m['from'].get('address', ''), name=m['from'].get('name', ''))
        to_addrs = [MessageAddress(address=t.get('address', ''), name=t.get('name', '')) for t in m.get('to', [])]
        return Message(id=m['id'], account_id=m['accountId'], msgid=m['msgid'], from_address=from_addr, to=to_addrs, subject=m['subject'], intro=m['intro'], seen=m['seen'], is_deleted=m['isDeleted'], has_attachments=m.get('hasAttachments', False), size=m['size'], download_url=m.get('downloadUrl', ''), created_at=m['createdAt'], updated_at=m['updatedAt'])


    def mark_message_as_seen(self, token: str, message_id: str, seen: bool = True):
        """Atualiza o status de 'visto' de uma mensagem."""
        self.logger.info(f"Marcando mensagem {message_id} como {'vista' if seen else 'não vista'}...")
        payload = {"seen": seen}
        headers_patch = {"Content-Type": "application/merge-patch+json"}
        # O método _request lida com os headers padrão, mas podemos passar headers adicionais
        self.session.headers.update(headers_patch)
        response = self._request("PATCH", f"{self.endpoints['messages']}/{message_id}", token=token, json=payload)
        self.session.headers.pop("Content-Type") # Limpa para não afetar outras requisições
        return response

    # --- Métodos de Alto Nível (Helpers) ---

    def create_random_account(self, password: Optional[str] = None, max_attempts: int = 20, delay: int = 1) -> AuthenticatedSession:
        """Cria uma conta com endereço aleatório de forma independente com tratamento de erros."""
        try:
            domains = self.get_domains()
        except MailTmAPIException:
            raise
        except Exception as e:
            raise wrap_exception(
                e, MailTmAPIException,
                "Erro ao buscar domínios para conta aleatória"
            )
        
        if not domains:
            raise MailTmAPIException(
                "Nenhum domínio disponível para criar conta.",
                details={"domains_count": 0}
            )
        domain = domains[0].domain

        final_password = password or ''.join(random.choices(string.ascii_letters + string.digits, k=get_config().api.mail_tm.password_length))

        for attempt in range(1, max_attempts + 1):
            local_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=get_config().api.mail_tm.username_length))
            address = f"{local_part}@{domain}"
            try:
                self.logger.info(f"Tentativa {attempt}: criando conta {address}...")
                return self.create_account(address, final_password)
            except MailTmAPIException as e:
                if "422" in str(e) or "already exists" in str(e).lower():
                    self.logger.aviso(f"E-mail {address} já existe. Tentando outro...")
                    time.sleep(delay)
                    continue
                else:
                    raise
            except Exception as e:
                raise wrap_exception(
                    e, MailTmAPIException,
                    "Erro inesperado ao criar conta aleatória",
                    attempt=attempt, address=address
                )
        
        raise MailTmAPIException(
            "Falha ao criar conta aleatória após várias tentativas.",
            details={"max_attempts": max_attempts, "domain": domain}
        )
    
    def wait_for_message(self, token: str, timeout: int = 60, interval: int = 5, filter_func: Optional[Callable[[Message], bool]] = None) -> Optional[Message]:
        """Aguarda até que uma nova mensagem chegue, usando um token com tratamento de erros."""
        self.logger.info(f"Aguardando mensagem por até {timeout} segundos...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                messages = self.get_messages(token)
            except MailTmAPIException as e:
                self.logger.aviso(f"Erro ao buscar mensagens: {e}. Tentando novamente...")
                time.sleep(interval)
                continue
            except Exception as e:
                self.logger.erro(f"Erro inesperado ao buscar mensagens: {e}")
                time.sleep(interval)
                continue
            
            try:
                if filter_func:
                    messages = [m for m in messages if filter_func(m)]
            except Exception as e:
                self.logger.aviso(f"Erro ao aplicar filtro: {e}")
            
            if messages:
                self.logger.info("Mensagem recebida!")
                
                return messages[0]
            time.sleep(interval)

        self.logger.aviso("Nenhuma mensagem recebida dentro do tempo limite.")
        return None
    
    def filter_messages(
        self,
        token: str,
        subject_contains: Optional[str] = None,
        from_address: Optional[str] = None
    ) -> List[Message]:
        """
        Filtra mensagens já recebidas.
        
        Args:
            token: Token de autenticação
            subject_contains: Filtro para assunto
            from_address: Filtro para endereço do remetente
            
        Returns:
            List[Message]: Lista de mensagens filtradas
        """
        messages = self.get_messages(token)
        
        if subject_contains:
            messages = [
                m for m in messages 
                if subject_contains.lower() in m.subject.lower()
            ]
        
        if from_address:
            messages = [
                m for m in messages 
                if from_address.lower() in m.from_address.address.lower()
            ]
        
        return messages