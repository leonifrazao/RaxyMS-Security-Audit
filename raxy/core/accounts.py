"""Carregamento estruturado das contas definidas em arquivo simples.

Cada linha valida (ignorando vazias ou iniciadas em ``#``) segue o formato::

    email:senha

Espacos nas extremidades sao desconsiderados e linhas malformadas sao ignoradas.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

_PERFIL_SEGURO_RE = re.compile(r"[^a-z0-9._-]+")


@dataclass(frozen=True)
class Conta:
    """Representa uma conta com email, senha e identificador de perfil."""

    email: str
    senha: str
    id_perfil: str



def carregar_contas(caminho_arquivo: str | Path) -> List[Conta]:
    """Lê o arquivo de contas e retorna a lista de :class:`Conta`.

    Args:
        caminho_arquivo: Caminho para o arquivo texto contendo as credenciais.

    Returns:
        Lista de ``Conta`` carregadas, ignorando linhas inválidas.

    Raises:
        FileNotFoundError: Quando o arquivo informado não existe.
    """

    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    contas: List[Conta] = []
    with caminho.open("r", encoding="utf-8") as handle:
        for linha_bruta in handle:
            linha = linha_bruta.strip()
            if not linha or linha.startswith("#"):
                continue
            if ":" not in linha:
                continue
            email, senha = (parte.strip() for parte in linha.split(":", 1))
            if not email or not senha:
                continue
            email_normalizado = email.strip().lower()
            if not email_normalizado:
                identificador = "perfil"
            else:
                substituido = email_normalizado.replace("@", "_at_")
                base = _PERFIL_SEGURO_RE.sub("_", substituido).strip("_")
                if not base:
                    base = "perfil"

                sufixo = hashlib.sha1(email_normalizado.encode("utf-8")).hexdigest()[:6]
                tamanho_maximo = 80
                limite_base = max(1, tamanho_maximo - len(sufixo) - 1)
                base_compactada = base[:limite_base]
                identificador = (
                    f"{base_compactada}_{sufixo}" if base_compactada else sufixo
                )

            contas.append(Conta(email=email, senha=senha, id_perfil=identificador))

    return contas


__all__ = ["Conta", "carregar_contas"]
