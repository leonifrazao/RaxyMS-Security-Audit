"""Implementações de repositório baseadas em arquivos texto."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence

from domain import Conta


def carregar_contas(caminho_arquivo: str | Path) -> list[Conta]:
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    contas: list[Conta] = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or ":" not in linha:
            continue

        email, senha = (parte.strip() for parte in linha.split(":", 1))
        if not email or not senha:
            continue

        base = email.lower().replace("@", "_at_")
        id_perfil = re.sub(r"[^a-z0-9._-]+", "_", base).strip("_") or "perfil"
        contas.append(Conta(email=email, senha=senha, id_perfil=id_perfil, proxy=''))

    return contas

from interfaces.repositories import IContaRepository, IHistoricoPontuacaoRepository

__all__ = [
    "ArquivoContaRepository",
    "HistoricoPontuacaoMemoriaRepository",
    "carregar_contas",
]


class ArquivoContaRepository(IContaRepository):
    """Realiza operações de persistência em um arquivo ``email:senha``."""

    def __init__(self, caminho_arquivo: str | Path) -> None:
        self._caminho = Path(caminho_arquivo)

    def listar(self) -> list[Conta]:
        return carregar_contas(self._caminho)

    def salvar(self, conta: Conta) -> Conta:
        contas = {item.email: item for item in self.listar()}
        contas[conta.email] = conta
        self._persistir(contas.values())
        return conta

    def salvar_varias(self, contas: Iterable[Conta]) -> Sequence[Conta]:
        existentes = {item.email: item for item in self.listar()}
        for conta in contas:
            existentes[conta.email] = conta
        self._persistir(existentes.values())
        return list(existentes.values())

    def remover(self, conta: Conta) -> None:
        contas = [item for item in self.listar() if item.email != conta.email]
        self._persistir(contas)

    def _persistir(self, contas: Iterable[Conta]) -> None:
        linhas = [f"{conta.email}:{conta.senha}\n" for conta in contas]
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._caminho.open("w", encoding="utf-8") as handle:
            handle.writelines(linhas)


class HistoricoPontuacaoMemoriaRepository(IHistoricoPontuacaoRepository):
    """Implementa o registro de pontos em memória (útil para testes)."""

    def __init__(self) -> None:
        self._ultimos: dict[str, int] = {}

    def registrar_pontos(self, conta: Conta, pontos: int) -> None:
        self._ultimos[conta.email] = pontos

    def obter_ultimo_total(self, conta: Conta) -> int | None:
        return self._ultimos.get(conta.email)
