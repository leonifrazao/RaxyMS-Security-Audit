# mailtm_service.py
import requests
import logging
import random
import string
import time
from typing import List, Optional, Callable
from raxy.domain.mailtm_data import Domain, Account, AuthenticatedSession, Message, MessageAddress

# Importando os dataclasses do arquivo de modelos
# from mailtm_models import Domain, Account, AuthenticatedSession, Message, MessageAddress

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MailTmError(Exception):
    """Exceção base para erros específicos da API Mail.tm."""
    pass

class MailTm:
    """
    Um wrapper Python stateless para a API Mail.tm.
    
    Esta classe não armazena estado (como tokens ou IDs de conta). Cada método
    recebe toda a informação necessária para operar, tornando o uso mais flexível e previsível.
    """
    
    def __init__(self):
        """Inicializa o cliente da API."""
        self.base_url = "https://api.mail.tm"
        self.session = requests.Session()

    def _request(self, method: str, endpoint: str, token: Optional[str] = None, **kwargs):
        """Método central para realizar requisições HTTP."""
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
        except requests.exceptions.HTTPError as e:
            error_msg = f"Erro na API: {e.response.status_code} - {e.response.text}"
            logging.error(f"Erro HTTP ao acessar {url}: {error_msg}")
            raise MailTmError(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"Erro de conexão: {e}"
            logging.error(f"Erro de conexão ao acessar {url}: {e}")
            raise MailTmError(error_msg) from e

    # --- Gerenciamento de Domínios ---
    
    def get_domains(self) -> List[Domain]:
        """Recupera a lista de domínios disponíveis."""
        logging.info("Buscando domínios disponíveis...")
        response = self._request("GET", "/domains")
        if isinstance(response, dict) and "hydra:member" in response:
            return [Domain(id=d['id'], domain=d['domain'], is_active=d['isActive'], is_private=d['isPrivate'], created_at=d['createdAt'], updated_at=d['updatedAt']) for d in response['hydra:member']]
        return []

    # --- Gerenciamento de Contas e Autenticação ---

    def create_account(self, address: str, password: str) -> AuthenticatedSession:
        """Cria uma nova conta e retorna uma sessão autenticada."""
        logging.info(f"Criando conta para o endereço: {address}")
        payload = {"address": address, "password": password}
        account_data = self._request("POST", "/accounts", json=payload)
        
        account = Account(id=account_data['id'], address=account_data['address'], is_disabled=account_data['isDisabled'], is_deleted=account_data['isDeleted'], created_at=account_data['createdAt'], updated_at=account_data['updatedAt'])
        
        token = self.get_token(address, password)
        logging.info(f"Conta {account.address} criada com sucesso.")
        
        return AuthenticatedSession(account=account, token=token)

    def get_token(self, address: str, password: str) -> str:
        """Obtém um token JWT para uma conta existente."""
        logging.info(f"Obtendo token para {address}...")
        payload = {"address": address, "password": password}
        response = self._request("POST", "/token", json=payload)
        
        token = response.get("token")
        if not token:
            raise MailTmError("Falha ao obter o token.")
        return token

    def get_me(self, token: str) -> Account:
        """Recupera os detalhes da conta associada a um token."""
        logging.info("Buscando detalhes da conta autenticada (/me)...")
        me_data = self._request("GET", "/me", token=token)
        return Account(id=me_data['id'], address=me_data['address'], is_disabled=me_data['isDisabled'], is_deleted=me_data['isDeleted'], created_at=me_data['createdAt'], updated_at=me_data['updatedAt'])


    def delete_account(self, session: AuthenticatedSession) -> None:
        """Exclui a conta associada a uma sessão autenticada."""
        account_id = session.account.id
        logging.info(f"Excluindo a conta {account_id}...")
        self._request("DELETE", f"/accounts/{account_id}", token=session.token)
        logging.info(f"Conta {session.account.address} ({account_id}) excluída com sucesso.")

    # --- Gerenciamento de Mensagens ---
    
    def get_messages(self, token: str, page: int = 1) -> List[Message]:
        """Recupera uma coleção de mensagens para a conta associada a um token."""
        logging.info(f"Buscando mensagens na página {page}...")
        response = self._request("GET", f"/messages?page={page}", token=token)
        
        messages = []
        if isinstance(response, dict) and "hydra:member" in response:
            for m in response['hydra:member']:
                from_addr = MessageAddress(address=m['from'].get('address', ''), name=m['from'].get('name', ''))
                to_addrs = [MessageAddress(address=t.get('address', ''), name=t.get('name', '')) for t in m.get('to', [])]
                messages.append(Message(id=m['id'], account_id=m['accountId'], msgid=m['msgid'], from_address=from_addr, to=to_addrs, subject=m['subject'], intro=m['intro'], seen=m['seen'], is_deleted=m['isDeleted'], has_attachments=m.get('hasAttachments', False), size=m['size'], download_url=m.get('downloadUrl', ''), created_at=m['createdAt'], updated_at=m['updatedAt']))
        return messages


    def get_message(self, token: str, message_id: str) -> Message:
        """Recupera os detalhes de uma mensagem específica pelo seu ID."""
        logging.info(f"Buscando detalhes da mensagem {message_id}...")
        m = self._request("GET", f"/messages/{message_id}", token=token)
        from_addr = MessageAddress(address=m['from'].get('address', ''), name=m['from'].get('name', ''))
        to_addrs = [MessageAddress(address=t.get('address', ''), name=t.get('name', '')) for t in m.get('to', [])]
        return Message(id=m['id'], account_id=m['accountId'], msgid=m['msgid'], from_address=from_addr, to=to_addrs, subject=m['subject'], intro=m['intro'], seen=m['seen'], is_deleted=m['isDeleted'], has_attachments=m.get('hasAttachments', False), size=m['size'], download_url=m.get('downloadUrl', ''), created_at=m['createdAt'], updated_at=m['updatedAt'])


    def mark_message_as_seen(self, token: str, message_id: str, seen: bool = True):
        """Atualiza o status de 'visto' de uma mensagem."""
        logging.info(f"Marcando mensagem {message_id} como {'vista' if seen else 'não vista'}...")
        payload = {"seen": seen}
        headers_patch = {"Content-Type": "application/merge-patch+json"}
        # O método _request lida com os headers padrão, mas podemos passar headers adicionais
        self.session.headers.update(headers_patch)
        response = self._request("PATCH", f"/messages/{message_id}", token=token, json=payload)
        self.session.headers.pop("Content-Type") # Limpa para não afetar outras requisições
        return response

    # --- Métodos de Alto Nível (Helpers) ---

    def create_random_account(self, password: Optional[str] = None, max_attempts: int = 20, delay: int = 1) -> AuthenticatedSession:
        """Cria uma conta com endereço aleatório de forma independente."""
        domains = self.get_domains()
        if not domains:
            raise MailTmError("Nenhum domínio disponível para criar conta.")
        domain = domains[0].domain

        final_password = password or ''.join(random.choices(string.ascii_letters + string.digits, k=12))

        for attempt in range(1, max_attempts + 1):
            local_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            address = f"{local_part}@{domain}"
            try:
                logging.info(f"Tentativa {attempt}: criando conta {address}...")
                return self.create_account(address, final_password)
            except MailTmError as e:
                if "422" in str(e) or "already exists" in str(e).lower():
                    logging.warning(f"E-mail {address} já existe. Tentando outro...")
                    time.sleep(delay)
                    continue
                else:
                    raise
        raise MailTmError("Falha ao criar conta aleatória após várias tentativas.")
    
    def wait_for_message(self, token: str, timeout: int = 60, interval: int = 5, filter_func: Optional[Callable[[Message], bool]] = None) -> Optional[Message]:
        """Aguarda até que uma nova mensagem chegue, usando um token."""
        logging.info(f"Aguardando mensagem por até {timeout} segundos...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            messages = self.get_messages(token)
            if filter_func:
                messages = [m for m in messages if filter_func(m)]
            if messages:
                logging.info("Mensagem recebida!")
                return messages[0]
            time.sleep(interval)

        logging.warning("Nenhuma mensagem recebida dentro do tempo limite.")
        return None