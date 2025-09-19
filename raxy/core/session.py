"""Ferramentas para capturar cookies e executar requests autenticadas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import urljoin

from botasaurus.browser import Driver

from .config import REWARDS_BASE_URL
from .helpers import (
    extract_request_verification_token,
    get_env_bool,
)
from .logging import log
from .profiles import GerenciadorPerfil


@dataclass(slots=True)
class SessaoSolicitacoes:
    """Representa o contexto HTTP derivado de uma sessao autenticada."""

    perfil: str
    cookies: Dict[str, str]
    user_agent: str
    url_base: str = REWARDS_BASE_URL
    request_verification_token: Optional[str] = None


@dataclass(slots=True, frozen=True)
class ParametrosManualSolicitacao:
    """Guarda os dados necessários para montar requisições manuais via Botasaurus."""

    perfil: str
    url_base: str
    user_agent: str
    headers: Mapping[str, str]
    cookies: Mapping[str, str]
    verification_token: Optional[str]
    palavras_erro: tuple[str, ...]
    interativo: bool


DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

REQUEST_OPTIONS = {
    "raise_exception": True,
    "create_error_logs": False,
    "output": None,
}


class GerenciadorSolicitacoesRewards:
    """Captura cookies do navegador e prepara clientes HTTP."""

    def __init__(self, perfil: str, driver: Driver):
        """Inicializa o gerenciador com o perfil e o driver em uso.

        Args:
            perfil: Identificador do perfil botasaurus utilizado na automação.
            driver: Instância ativa do navegador controlado pelo botasaurus.
        """

        self.perfil = perfil
        self.driver = driver
        self._dados_sessao: Optional[SessaoSolicitacoes] = None

    def capturar(self) -> SessaoSolicitacoes:
        """Coleta cookies e user-agent da sessão do navegador.

        Returns:
            Instância de :class:`SessaoSolicitacoes` com os dados capturados.
        """

        cookies = self.driver.get_cookies_dict()
        user_agent = getattr(self.driver, "user_agent", None) or GerenciadorPerfil.garantir_agente_usuario(
            self.perfil
        )
        token: Optional[str] = None
        try:
            html_atual = getattr(self.driver, "page_source", None)
        except Exception as exc:  # pragma: no cover - depende do driver
            html_atual = None
            log.debug("Nao foi possivel ler page_source", detalhe=str(exc))
        if html_atual:
            token = extract_request_verification_token(html_atual)

        if not token:
            requisicoes = getattr(self.driver, "requests", None)
            if requisicoes is not None:
                try:
                    url_atual = getattr(self.driver, "current_url", None) or REWARDS_BASE_URL
                    retorno = requisicoes.get(url_atual)
                except Exception as exc:  # pragma: no cover - depende do ambiente
                    retorno = None
                    log.debug("Falha ao requisitar HTML para token", detalhe=str(exc))
                else:
                    html_fresco = getattr(retorno, "text", None)
                    if html_fresco:
                        token = extract_request_verification_token(html_fresco)

        log.debug(
            "Cookies capturados para sessao HTTP",
            perfil=self.perfil,
            total_cookies=len(cookies),
        )
        if token:
            log.debug("Token antifalsificacao capturado", tamanho=len(token))

        self._dados_sessao = SessaoSolicitacoes(
            perfil=self.perfil,
            cookies=cookies,
            user_agent=user_agent,
            request_verification_token=token,
        )
        return self._dados_sessao

    @property
    def dados_sessao(self) -> Optional[SessaoSolicitacoes]:
        """Retorna os dados de sessao em cache, se existentes."""

        return self._dados_sessao

    def parametros_manuais(
        self,
        *,
        url_base: Optional[str] = None,
        palavras_erro: Optional[Iterable[str]] = None,
        interativo: Optional[bool] = None,
    ) -> ParametrosManualSolicitacao:
        """Retorna os elementos prontos para montar chamadas manuais."""

        if self._dados_sessao is None:
            self.capturar()

        if self._dados_sessao is None:
            raise RuntimeError("Sessao HTTP indisponivel; execute 'capturar' antes de coletar parametros")

        sessao = self._dados_sessao
        url_referencia = (url_base or sessao.url_base).rstrip("/") or REWARDS_BASE_URL

        cabecalho = dict(DEFAULT_HEADERS)
        cabecalho["User-Agent"] = sessao.user_agent
        cabecalho.setdefault("Referer", url_referencia)

        palavras = tuple(
            palavra.strip().lower()
            for palavra in (palavras_erro or [])
            if isinstance(palavra, str) and palavra.strip()
        )

        if interativo is None:
            env_flag = get_env_bool("RAXY_SOLICITACOES_INTERATIVAS", padrao=True)
            interativo_final = bool(env_flag)
        else:
            interativo_final = bool(interativo)

        return ParametrosManualSolicitacao(
            perfil=sessao.perfil,
            url_base=url_referencia,
            user_agent=sessao.user_agent,
            headers=cabecalho,
            cookies=dict(sessao.cookies),
            verification_token=sessao.request_verification_token,
            palavras_erro=palavras,
            interativo=interativo_final,
        )


__all__ = [
    "SessaoSolicitacoes",
    "GerenciadorSolicitacoesRewards",
    "ParametrosManualSolicitacao",
]
