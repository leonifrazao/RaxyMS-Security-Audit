"""
Gerenciamento de perfis para o SessionManagerService.

Responsável por criar, atualizar e gerenciar perfis de navegador.
"""

from __future__ import annotations
from typing import Optional, Any, Dict
import time
from random_user_agent.user_agent import UserAgent
from botasaurus.profiles import Profiles

from raxy.domain.accounts import Conta
from raxy.core.config import get_config
from raxy.core.exceptions import ProfileException, wrap_exception
from raxy.core.logging import debug_log
from raxy.interfaces.services import IMailTmService, ILoggingService
from raxy.services.base_service import BaseService


class ProfileManager(BaseService):
    """
    Gerencia perfis de navegador e User-Agents.
    
    Responsável por:
    - Criar novos perfis
    - Atualizar perfis existentes
    - Gerar User-Agents únicos
    - Persistir dados de perfil
    """
    
    def __init__(
        self, 
        conta: Conta,
        mail_service: Optional[IMailTmService] = None,
        logger: Optional[ILoggingService] = None,
        event_bus: Optional[Any] = None
    ):
        """
        Inicializa o gerenciador de perfis.
        
        Args:
            conta: Conta associada ao perfil
            mail_service: Serviço de email temporário (opcional)
            logger: Serviço de logging (opcional)
            event_bus: Event Bus para publicação de eventos
        """
        super().__init__(logger)
        self.conta = conta
        self._mail_service = mail_service
        self._event_bus = event_bus
        
        # Provedor de User-Agent
        session_config = get_config().session
        self._ua_provider = UserAgent(
            limit=session_config.ua_limit,
            software_names=session_config.get_softwares_enums(),
            operating_systems=session_config.get_sistemas_enums(),
        )
    
    def _publish_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Publica evento no Event Bus se disponível."""
        if self._event_bus and hasattr(self._event_bus, 'publish'):
            try:
                self._event_bus.publish(event_name, data)
            except Exception:
                pass
    
    @debug_log(log_args=True, log_result=False, log_duration=True)
    def garantir_perfil(self, perfil: str) -> list[str]:
        """
        Garante que o perfil exista e retorna os argumentos de linha de comando.
        
        Args:
            perfil: Nome do perfil
            
        Returns:
            Lista com argumentos de linha de comando para o User-Agent
            
        Raises:
            ProfileException: Se houver erro ao acessar/criar perfil
        """
        if not perfil:
            raise ProfileException(
                "Perfil deve ser informado", 
                details={"conta": self.conta.email}
            )
        
        try:
            perfil_data = Profiles.get_profile(perfil)
        except Exception as e:
            raise wrap_exception(
                e, ProfileException, 
                "Erro ao acessar perfil", 
                perfil=perfil, 
                conta=self.conta.email
            )
        
        if not perfil_data:
            agente = self._criar_novo_perfil(perfil)
        else:
            agente = self._obter_ou_regenerar_ua(perfil, perfil_data)
        
        # Retorna o argumento User-Agent no formato esperado pelo Botasaurus
        return [f"--user-agent={agente}"]
    
    def _criar_novo_perfil(self, perfil: str) -> str:
        """
        Cria um novo perfil com User-Agent e credenciais.
        
        Args:
            perfil: Nome do perfil
            
        Returns:
            User-Agent gerado
            
        Raises:
            ProfileException: Se houver erro ao criar perfil
        """
        if not self._mail_service:
            self.logger.erro("IMailTmService não foi fornecido. Não é possível criar novo perfil.")
            raise ProfileException(
                "IMailTmService é obrigatório para garantir um novo perfil.",
                details={"perfil": perfil, "conta": self.conta.email}
            )
        
        self.logger.info(f"Perfil '{perfil}' não encontrado. Criando novo perfil.")
        
        try:
            # 1. Gera um novo UA
            novo_ua = self._ua_provider.get_random_user_agent()
            
            # 2. Persiste os dados no perfil
            Profiles.set_profile(perfil, {
                "UA": novo_ua, 
                "email": self.conta.email, 
                "senha": self.conta.senha,
            })
            
            self.logger.sucesso(f"Novo perfil '{perfil}' criado com UA e credenciais salvas.")
            
            self._publish_event("profile.created", {
                "profile_id": perfil,
                "account_id": self.conta.email,
                "user_agent": novo_ua,
                "timestamp": time.time(),
            })
            
            return novo_ua
            
        except Exception as e:
            raise wrap_exception(
                e, ProfileException,
                "Erro ao criar novo perfil",
                perfil=perfil, 
                conta=self.conta.email
            )
    
    def _obter_ou_regenerar_ua(self, perfil: str, perfil_data: dict) -> str:
        """
        Obtém User-Agent do perfil ou regenera se necessário.
        
        Args:
            perfil: Nome do perfil
            perfil_data: Dados do perfil existente
            
        Returns:
            User-Agent obtido ou regenerado
        """
        agente = perfil_data.get("UA")
        
        if not agente:
            # Caso extremo: perfil existe mas UA foi perdido, regenera e salva.
            agente = self._ua_provider.get_random_user_agent()
            Profiles.set_profile(perfil, {**perfil_data, "UA": agente})
            self.logger.aviso(f"User-Agent regenerado e salvo para o perfil '{perfil}'.")
            
            self._publish_event("profile.ua_regenerated", {
                "profile_id": perfil,
                "account_id": self.conta.email,
                "user_agent": agente,
                "timestamp": time.time(),
            })
        
        return agente
    
    def obter_dados_perfil(self, perfil: str) -> dict:
        """
        Obtém os dados completos de um perfil.
        
        Args:
            perfil: Nome do perfil
            
        Returns:
            Dicionário com dados do perfil
        """
        try:
            return Profiles.get_profile(perfil) or {}
        except Exception as e:
            self.logger.erro(f"Erro ao obter dados do perfil: {e}", perfil=perfil)
            return {}
