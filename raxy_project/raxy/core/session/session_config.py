"""
Configurações para o SessionManagerService.

Define constantes e configurações usadas no gerenciamento de sessões.
"""

from __future__ import annotations
from random_user_agent.params import OperatingSystem, SoftwareName


class SessionConfig:
    """Configurações do serviço de sessão."""
    
    # Softwares padrão para User-Agent
    SOFTWARES_PADRAO = [SoftwareName.EDGE.value]
    
    # Sistemas operacionais padrão
    SISTEMAS_PADRAO = [
        OperatingSystem.WINDOWS.value,
        OperatingSystem.LINUX.value,
        OperatingSystem.MACOS.value,
    ]
    
    # URLs principais
    REWARDS_URL = "https://rewards.bing.com/"
    BING_URL = "https://www.bing.com"
    BING_FLYOUT_URL = (
        "https://www.bing.com/rewards/panelflyout?"
        "channel=bingflyout&partnerId=BingRewards&"
        "isDarkMode=1&requestedLayout=onboarding&form=rwfobc"
    )
    
    # Configurações de tentativas
    MAX_LOGIN_ATTEMPTS = 5
    
    # Timeouts e esperas
    UA_LIMIT = 100
    
    # Títulos de páginas esperados
    REWARDS_TITLE = "microsoft rewards"
    VERIFY_EMAIL_TITLE = "verify your email"
    PROTECT_ACCOUNT_TITLE = "let's protect your account"
    
    # Seletores CSS principais
    SELECTORS = {
        # Login
        "email_input": "input[type='email'], #i0116",
        "password_input": "input[type='password'], #i0118",
        "submit_button": "button[type='submit'], #idSIButton9",
        
        # Verificação
        "email_verify_link": "#view > div > span:nth-child(6) > div > span",
        "skip_link": "a[id='iShowSkip']",
        "primary_button": "button[data-testid='primaryButton']",
        
        # Status
        "id_s_span": 'span[id="id_s"]',
        "role_presentation": "span[role='presentation']",
        
        # Rewards
        "join_now": 'a[class="joinNowText"]',
        "card_0": 'div[id="Card_0"]'
    }
