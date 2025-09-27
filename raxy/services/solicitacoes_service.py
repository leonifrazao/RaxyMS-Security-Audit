"""Serviço que coordena solicitações autenticadas ao Rewards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from interfaces.services import IGerenciadorSolicitacoesService
from services.session_service import ParametrosManualSolicitacao, SessaoSolicitacoes


@dataclass(slots=True)
class DadosSessao:
    """Representa dados adicionais capturados durante o login."""

    request_verification_token: str | None = None
    extras: Mapping[str, Any] | None = None


class GerenciadorSolicitacoesRewards(IGerenciadorSolicitacoesService):
    """Mantém estado derivado da sessão para requisições manuais."""

    def __init__(self, sessao: SessaoSolicitacoes, *, palavras_erro: tuple[str, ...] = (), interativo: bool = False) -> None:
        self._sessao = sessao
        self._palavras_erro = palavras_erro
        self._interativo = interativo
        token = getattr(sessao, "verification_token", None)
        self._dados_sessao = DadosSessao(request_verification_token=token)

    def parametros_manuais(self, *, interativo: bool | None = None) -> ParametrosManualSolicitacao:
        return self._sessao.parametros_manuais(
            palavras_erro=self._palavras_erro,
            interativo=self._interativo if interativo is None else interativo,
        )

    @property
    def dados_sessao(self) -> DadosSessao | None:
        return self._dados_sessao


__all__ = ["GerenciadorSolicitacoesRewards", "DadosSessao"]
