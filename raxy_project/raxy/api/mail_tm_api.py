import requests
import logging

# Configuração básica de logging para depuração
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MailTmError(Exception):
    """Exceção base para erros específicos da API Mail.tm."""
    pass

class MailTm:
    """
    Um wrapper Python para a API Mail.tm (api.mail.tm), otimizado para eficiência.
    
    Esta classe fornece métodos para interagir com os endpoints da API Mail.tm,
    gerenciando automaticamente o token de autenticação e usando uma única sessão
    HTTP para reutilização de conexão.
    """
    
    def __init__(self):
        """Inicializa o cliente da API."""
        self.base_url = "https://api.mail.tm"
        self.token = None
        self.account_id = None
        self.address = None
        
        # Usa uma sessão para otimizar conexões
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def _request(self, method, endpoint, **kwargs):
        """
        Método central para realizar requisições HTTP, com tratamento de erros otimizado.
        """
        url = f"{self.base_url}{endpoint}"
        
        # Adiciona o token de autorização se estiver disponível
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
            
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()  # Lança exceção para códigos de erro HTTP (4xx ou 5xx)
            
            # Retorna None para respostas 204 (No Content)
            if response.status_code == 204:
                return None
                
            return response.json()
        except requests.exceptions.HTTPError as e:
            logging.error(f"Erro HTTP ao acessar {url}: {e.response.status_code} {e.response.text}")
            raise MailTmError(f"Erro na API: {e.response.status_code} - {e.response.text}") from e
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão ao acessar {url}: {e}")
            raise MailTmError(f"Erro de conexão: {e}") from e

    # --- Gerenciamento de Domínios ---
    
    def get_domains(self):
        """
        Recupera a primeira página de domínios disponíveis.
        
        Retorna:
            list: Uma lista de dicionários, cada um representando um domínio.
        """
        logging.info("Buscando domínios disponíveis...")
        response = self._request("GET", "/domains")
        
        if isinstance(response, dict) and "hydra:member" in response:
            return response.get("hydra:member", [])
        elif isinstance(response, list):
            return response
        else:
            logging.warning("Formato da resposta de /domains inesperado. Retornando lista vazia.")
            return []

    # --- Gerenciamento de Contas e Autenticação ---

    def create_account(self, address, password):
        """
        Cria uma nova conta e obtém o token de autenticação.
        """
        logging.info(f"Criando conta para o endereço: {address}")
        payload = {"address": address, "password": password}
        account_data = self._request("POST", "/accounts", json=payload)
        
        self.account_id = account_data.get("id")
        self.address = account_data.get("address")
        
        self.get_token(address, password)
        logging.info(f"Conta {self.address} criada com sucesso. Token obtido.")
        
        return account_data

    def get_token(self, address, password):
        """
        Obtém um token JWT para uma conta existente.
        """
        logging.info(f"Obtendo token para {address}...")
        payload = {"address": address, "password": password}
        response = self._request("POST", "/token", json=payload)
        
        self.token = response.get("token")
        if not self.token:
            raise MailTmError("Falha ao obter o token. Resposta da API não continha o token.")
            
        me_data = self.get_me()
        self.account_id = me_data.get("id")
        self.address = me_data.get("address")
        
        return self.token

    def get_me(self):
        """
        Recupera os detalhes da conta associada ao token atual.
        """
        if not self.token:
            raise MailTmError("Autenticação necessária. Obtenha um token primeiro.")
        logging.info("Buscando detalhes da conta autenticada (/me)...")
        return self._request("GET", "/me")

    def delete_account(self):
        """
        Exclui a conta associada ao token atual.
        """
        if not self.token or not self.account_id:
            raise MailTmError("Autenticação necessária. Crie uma conta ou obtenha um token primeiro.")
        
        logging.info(f"Excluindo a conta {self.account_id}...")
        self._request("DELETE", f"/accounts/{self.account_id}")
        logging.info(f"Conta {self.address} ({self.account_id}) excluída com sucesso.")
        
        self.token = None
        self.account_id = None
        self.address = None

    # --- Gerenciamento de Mensagens ---
    
    def get_messages(self, page=1):
        """
        Recupera uma coleção de mensagens para a conta autenticada.
        """
        if not self.token:
            raise MailTmError("Autenticação necessária. Obtenha um token primeiro.")
        logging.info(f"Buscando mensagens na página {page}...")
        response = self._request("GET", f"/messages?page={page}")
        
        if isinstance(response, dict) and "hydra:member" in response:
            return response.get("hydra:member", [])
        elif isinstance(response, list):
            return response
        else:
            logging.warning("Formato da resposta de /messages inesperado. Retornando lista vazia.")
            return []


    def get_message(self, message_id):
        """
        Recupera os detalhes de uma mensagem específica pelo seu ID.
        """
        if not self.token:
            raise MailTmError("Autenticação necessária.")
        logging.info(f"Buscando detalhes da mensagem {message_id}...")
        return self._request("GET", f"/messages/{message_id}")

    def mark_message_as_seen(self, message_id, seen=True):
        """
        Atualiza o status de 'visto' de uma mensagem.
        """
        if not self.token:
            raise MailTmError("Autenticação necessária.")
        logging.info(f"Marcando mensagem {message_id} como {'vista' if seen else 'não vista'}...")
        payload = {"seen": seen}
        # CORREÇÃO: Define o Content-Type exigido pela API para esta requisição PATCH.
        headers = {"Content-Type": "application/merge-patch+json"}
        return self._request("PATCH", f"/messages/{message_id}", json=payload, headers=headers)