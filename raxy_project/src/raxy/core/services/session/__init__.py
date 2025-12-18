"""
Módulo de gerenciamento de sessão.

Fornece componentes de sessão para gerenciamento de login e perfis
do Microsoft Rewards.
"""

from raxy.core.services.session.session_utils import (
    extract_request_verification_token,
    replace_placeholders,
    normalize_credentials,
    is_valid_email
)
from raxy.core.services.session.profile_manager import ProfileManager
from raxy.core.services.session.browser_login_handler import BrowserLoginHandler
from raxy.core.services.session.request_executor import RequestExecutor

__all__ = [
    "ProfileManager", 
    "BrowserLoginHandler",
    "RequestExecutor",
    "extract_request_verification_token",
    "replace_placeholders",
    "normalize_credentials",
    "is_valid_email",
]
