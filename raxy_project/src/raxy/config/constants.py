"""
Constantes globais do sistema Raxy.

Este módulo centraliza todas as constantes 'hardcoded' do sistema,
facilitando a manutenção e a aplicação do princípio DRY.
"""

from typing import Dict, Set

# ============================================================================
# Definições de Domínio
# ============================================================================

# Ações válidas que o executor pode realizar
VALID_ACTIONS: Set[str] = {"login", "rewards", "bing", "flyout", "email"}

# Ambientes de execução suportados
VALID_ENVIRONMENTS: Set[str] = {"dev", "staging", "prod"}

# ============================================================================
# Seletores CSS (Web Scraping)
# ============================================================================

DEFAULT_SELECTORS: Dict[str, str] = {
    # Login Microsoft
    "email_input": "input[type='email'], #i0116",
    "password_input": "input[type='password'], #i0118",
    "submit_button": "button[type='submit'], #idSIButton9",
    
    # Verificação de Segurança
    "email_verify_link": "#view > div > span:nth-child(6) > div > span",
    "skip_link": "a[id='iShowSkip']",
    "primary_button": "button[data-testid='primaryButton']",
    
    # Status da Conta
    "id_s_span": 'span[id="id_s"]',
    "role_presentation": "span[role='presentation']",
    
    # Rewards e Pontos
    "join_now": 'a[class="joinNowText"]',
    "card_0": 'div[id="Card_0"]',
}

# ============================================================================
# Logging
# ============================================================================

LEVEL_VALUES: Dict[str, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "SUCCESS": 25,  # Nível customizado
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

LEVEL_NAMES: Dict[int, str] = {v: k for k, v in LEVEL_VALUES.items()}

# ============================================================================
# URLs e Endpoints
# ============================================================================

URLS = {
    "rewards_home": "https://rewards.bing.com/",
    "bing_home": "https://www.bing.com",
    "bing_flyout": (
        "https://www.bing.com/rewards/panelflyout?"
        "channel=bingflyout&partnerId=BingRewards&"
        "isDarkMode=1&requestedLayout=onboarding&form=rwfobc"
    ),
    "supabase_default": "https://supabase.io",
}

# ============================================================================
# Padrões e Timeouts
# ============================================================================

DEFAULTS = {
    "users_file": "users.txt",
    "proxy_cache": "proxy_cache.json",
    "log_format_date": "%Y-%m-%d %H:%M:%S",
    "timeout_api": 30,
    "timeout_element": 10,
}
