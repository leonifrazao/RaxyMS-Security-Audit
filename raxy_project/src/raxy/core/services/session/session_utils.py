"""
Funções utilitárias para o SessionManagerService.

Contém funções auxiliares usadas no gerenciamento de sessões.
"""

from __future__ import annotations
from typing import Any, Mapping
from botasaurus.soupify import soupify
from raxy.infrastructure.logging import get_logger

log = get_logger()


def extract_request_verification_token(html: str | None) -> str | None:
    """
    Extrai o token de verificação do HTML.
    
    Args:
        html: HTML da página
        
    Returns:
        Token de verificação ou None se não encontrado
    """
    if not html:
        return None
    
    try:
        soup = soupify(html)
        campo = soup.find("input", {"name": "__RequestVerificationToken"})
        if campo and campo.get("value"):
            return campo["value"].strip() or None
    except Exception as e:
        log.debug("Falha ao extrair token de verificação", erro=str(e))
        return None
    
    return None


def replace_placeholders(obj: Any, placeholders: Mapping[str, Any]) -> Any:
    """
    Substitui placeholders em um objeto recursivamente.
    
    Args:
        obj: Objeto a processar (string, dict, list, etc)
        placeholders: Dicionário de placeholders e seus valores
        
    Returns:
        Objeto com placeholders substituídos
    """
    if not placeholders:
        return obj
    
    if isinstance(obj, str):
        for k, v in placeholders.items():
            obj = obj.replace("{definir}", str(v)).replace("{"+str(k)+"}", str(v))
        return obj
    
    if isinstance(obj, dict):
        return {k: replace_placeholders(v, placeholders) for k, v in obj.items()}
    
    if isinstance(obj, list):
        return [replace_placeholders(v, placeholders) for v in obj]
    
    return obj


def normalize_credentials(email: str | None, senha: str | None) -> tuple[str, str]:
    """
    Normaliza credenciais removendo espaços.
    
    Args:
        email: Email a normalizar
        senha: Senha a normalizar
        
    Returns:
        Tupla (email_normalizado, senha_normalizada)
    """
    email_normalizado = str(email or "").strip()
    senha_normalizada = str(senha or "").strip()
    return email_normalizado, senha_normalizada


def is_valid_email(email: str) -> bool:
    """
    Valida se o email está no formato correto.
    
    Args:
        email: Email a validar
        
    Returns:
        True se válido, False caso contrário
    """
    return bool(email and "@" in email)
