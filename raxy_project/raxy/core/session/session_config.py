"""
Configurações para o SessionManagerService.

DEPRECATED: Este módulo é mantido apenas para compatibilidade.
Use raxy.core.config.get_config().session para configurações centralizadas.
"""

from __future__ import annotations
from random_user_agent.params import OperatingSystem, SoftwareName

from raxy.core.config import get_config


class _SessionConfigMeta(type):
    """Metaclass para permitir acesso a propriedades como atributos de classe."""
    
    @property
    def SOFTWARES_PADRAO(cls):
        """Retorna lista de softwares mapeados para enum."""
        config = get_config().session
        mapping = {
            "edge": SoftwareName.EDGE.value,
            "chrome": SoftwareName.CHROME.value,
            "firefox": SoftwareName.FIREFOX.value,
        }
        return [mapping.get(s.lower(), SoftwareName.EDGE.value) for s in config.softwares_padrao]
    
    @property
    def SISTEMAS_PADRAO(cls):
        """Retorna lista de sistemas operacionais mapeados para enum."""
        config = get_config().session
        mapping = {
            "windows": OperatingSystem.WINDOWS.value,
            "linux": OperatingSystem.LINUX.value,
            "macos": OperatingSystem.MACOS.value,
        }
        return [mapping.get(s.lower(), OperatingSystem.WINDOWS.value) for s in config.sistemas_padrao]
    
    @property
    def REWARDS_URL(cls):
        return get_config().session.rewards_url
    
    @property
    def BING_URL(cls):
        return get_config().session.bing_url
    
    @property
    def BING_FLYOUT_URL(cls):
        return get_config().session.bing_flyout_url
    
    @property
    def MAX_LOGIN_ATTEMPTS(cls):
        return get_config().session.max_login_attempts
    
    @property
    def UA_LIMIT(cls):
        return get_config().session.ua_limit
    
    @property
    def REWARDS_TITLE(cls):
        return get_config().session.rewards_title
    
    @property
    def VERIFY_EMAIL_TITLE(cls):
        return get_config().session.verify_email_title
    
    @property
    def PROTECT_ACCOUNT_TITLE(cls):
        return get_config().session.protect_account_title
    
    @property
    def SELECTORS(cls):
        return get_config().session.selectors


class SessionConfig(metaclass=_SessionConfigMeta):
    """
    DEPRECATED: Use raxy.core.config.get_config().session diretamente.
    
    Este wrapper mantém compatibilidade retroativa com código que usa
    SessionConfig.ATRIBUTO, redirecionando para a configuração centralizada.
    """
    pass
