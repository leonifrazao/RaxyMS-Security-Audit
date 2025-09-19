"""Helpers para lidar com o ``__RequestVerificationToken``."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

from botasaurus.soupify import soupify


def extract_request_verification_token(html: Optional[str]) -> Optional[str]:
    """Extrai o valor do ``__RequestVerificationToken`` de um HTML bruto."""

    if not html:
        return None

    try:
        soup = soupify(html)
    except Exception:  # pragma: no cover - parsing depende do HTML real
        return None

    if not soup:
        return None

    campo = soup.find("input", {"name": "__RequestVerificationToken"})
    if campo and "value" in campo.attrs:
        valor = campo["value"].strip()
        return valor or None
    return None


def ensure_payload_token(payload: Any, token: str) -> Tuple[Any, bool]:
    """Garante que um payload dict possua o ``__RequestVerificationToken``."""

    if isinstance(payload, Mapping):
        token_atual = payload.get("__RequestVerificationToken")
        if token_atual and token_atual not in {"{definir}", ""}:
            return payload, False

        atualizado = dict(payload)
        atualizado["__RequestVerificationToken"] = token
        return atualizado, True

    return payload, False


def ensure_token_header(
    headers: Optional[Mapping[str, str]],
    token: str,
) -> Dict[str, str]:
    """Garante que o header ``RequestVerificationToken`` esteja definido."""

    cabecalho = dict(headers or {})
    valor_atual = cabecalho.get("RequestVerificationToken")
    if not valor_atual or valor_atual == "{definir}":
        cabecalho["RequestVerificationToken"] = token
    return cabecalho


def inject_request_verification_token(
    method: str,
    params: Mapping[str, Any],
    headers: Optional[Mapping[str, str]],
    token: Optional[str],
) -> Tuple[Dict[str, Any], Optional[Dict[str, str]]]:
    """Insere o token antifalsificacao nos dados e headers aplicaveis."""

    if not token:
        return dict(params), dict(headers) if headers is not None else None

    if method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return dict(params), dict(headers) if headers is not None else None

    parametros = dict(params)
    utilizou_token = False

    for chave in ("data", "json"):
        payload = parametros.get(chave)
        payload_ajustado, inseriu = ensure_payload_token(payload, token)
        if inseriu:
            parametros[chave] = payload_ajustado
            utilizou_token = True

    if not utilizou_token:
        return parametros, dict(headers) if headers is not None else None

    headers_ajustados = ensure_token_header(headers, token)
    return parametros, headers_ajustados
