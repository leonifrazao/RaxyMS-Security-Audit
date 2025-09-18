"""Carregamento estruturado das contas definidas em arquivo simples.

Cada linha valida (ignorando vazias ou iniciadas em ``#``) segue o formato::

    email:senha

Espacos nas extremidades sao desconsiderados e linhas malformadas sao ignoradas.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class Conta:
    """Representa uma conta com email, senha e identificador de perfil."""

    email: str
    senha: str
    id_perfil: str


def _derivar_id_perfil(email: str) -> str:
    """Gera um identificador de perfil a partir do email fornecido.

    Args:
        email: Endereço de email da conta.

    Returns:
        String simplificada usada para nomear o perfil do navegador.
    """

    parte_local = email.split("@", 1)[0]
    return parte_local or email.replace("@", "_")


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
    for linha_bruta in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha_bruta.strip()
        if not linha or linha.startswith("#"):
            continue
        if ":" not in linha:
            continue
        email, senha = [parte.strip() for parte in linha.split(":", 1)]
        if not email or not senha:
            continue
        contas.append(Conta(email=email, senha=senha, id_perfil=_derivar_id_perfil(email)))

    return contas


__all__ = ["Conta", "carregar_contas"]
