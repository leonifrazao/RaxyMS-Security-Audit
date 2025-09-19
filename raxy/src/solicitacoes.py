"""Ferramentas para capturar cookies e executar requests autenticadas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import partialmethod
import json
from pathlib import Path
import traceback
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import urljoin

from botasaurus.beep_utils import beep_input
from botasaurus.browser import Driver
from botasaurus.request import Request, request
from botasaurus_requests.response import Response

from .config import REWARDS_BASE_URL
from .helpers import (
    extract_request_verification_token,
    get_env_bool,
    inject_request_verification_token,
)
from .logging import log
from .utilitarios import GerenciadorPerfil


@dataclass(slots=True)
class SessaoSolicitacoes:
    """Representa o contexto HTTP derivado de uma sessao autenticada."""

    perfil: str
    cookies: Dict[str, str]
    user_agent: str
    url_base: str = REWARDS_BASE_URL
    request_verification_token: Optional[str] = None


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
        token = self._capturar_token_verificacao()

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

    def _capturar_token_verificacao(self) -> Optional[str]:
        """Tenta capturar o ``__RequestVerificationToken`` da página atual."""

        html_atual = self._obter_html_atual()
        token = extract_request_verification_token(html_atual)
        if token:
            return token

        html_fresco = self._obter_html_via_request()
        return extract_request_verification_token(html_fresco)

    def _obter_html_atual(self) -> Optional[str]:
        """Obtém o HTML corrente exibido pelo navegador controlado."""

        try:
            return getattr(self.driver, "page_source", None)
        except Exception as exc:  # pragma: no cover - depende do driver
            log.debug("Nao foi possivel ler page_source", detalhe=str(exc))
            return None

    def _obter_html_via_request(self) -> Optional[str]:
        """Requisita o HTML diretamente via ``driver.requests`` como fallback."""

        requisicoes = getattr(self.driver, "requests", None)
        if requisicoes is None:
            return None

        try:
            url_atual = getattr(self.driver, "current_url", None) or REWARDS_BASE_URL
            retorno = requisicoes.get(url_atual)
        except Exception as exc:  # pragma: no cover - depende do ambiente
            log.debug("Falha ao requisitar HTML para token", detalhe=str(exc))
            return None

        return getattr(retorno, "text", None)

    @property
    def dados_sessao(self) -> Optional[SessaoSolicitacoes]:
        """Retorna os dados de sessao em cache, se existentes."""

        return self._dados_sessao

    def criar_cliente(
        self,
        url_base: Optional[str] = None,
        palavras_erro: Optional[Iterable[str]] = None,
        interativo: Optional[bool] = None,
    ) -> "ClienteSolicitacoesRewards":
        """Retorna um cliente HTTP pronto para uso com os cookies capturados.

        Args:
            url_base: URL alternativa para as requisições. Defaults para a base
                registrada na sessão.
            palavras_erro: Lista de palavras que indicam respostas indesejadas.
            interativo: Força o modo interativo dos prompts do botasaurus.

        Returns:
            Instância configurada de :class:`ClienteSolicitacoesRewards`.
        """

        if self._dados_sessao is None:
            self.capturar()

        if self._dados_sessao is None:
            raise RuntimeError("Sessao HTTP indisponivel; execute 'capturar' antes de criar o cliente")

        sessao = self._dados_sessao
        return ClienteSolicitacoesRewards(
            perfil=sessao.perfil,
            cookies=sessao.cookies,
            user_agent=sessao.user_agent,
            url_base=url_base or sessao.url_base,
            verification_token=sessao.request_verification_token,
            palavras_erro=palavras_erro,
            interativo=interativo,
        )


class ClienteSolicitacoesRewards:
    """Cliente HTTP estruturado sobre o decorator ``@request`` do Botasaurus."""

    _CABECALHO_PADRAO = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }

    _OPCOES_REQUEST = {
        "raise_exception": True,
        "create_error_logs": False,
        "output": None,
    }

    def __init__(
        self,
        *,
        perfil: str,
        cookies: Mapping[str, str],
        user_agent: str,
        url_base: str,
        verification_token: Optional[str] = None,
        palavras_erro: Optional[Iterable[str]] = None,
        interativo: Optional[bool] = None,
    ) -> None:
        """Configura o cliente HTTP autenticado reutilizando a sessão atual.

        Args:
            perfil: Nome/identificador do perfil associado aos cookies.
            cookies: Cookies capturados do navegador autenticado.
            user_agent: User-Agent utilizado pelo navegador.
            url_base: Base das URLs chamadas pela API.
            palavras_erro: Palavras que devem disparar alertas e logs detalhados.
            interativo: Controla prompts interativos (``True``/``False``/``None``).
        """

        self.perfil = perfil
        self.url_base = url_base.rstrip("/") or REWARDS_BASE_URL
        self._cookies = dict(cookies)
        self._verification_token = verification_token
        cabecalho_personalizado = dict(self._CABECALHO_PADRAO)
        cabecalho_personalizado["User-Agent"] = user_agent
        cabecalho_personalizado.setdefault("Referer", self.url_base)
        self._headers = cabecalho_personalizado
        self._palavras_erro = {
            palavra.lower()
            for palavra in (palavras_erro or [])
            if isinstance(palavra, str) and palavra.strip()
        }
        if interativo is None:
            flag = get_env_bool("RAXY_SOLICITACOES_INTERATIVAS", padrao=True)
            self._interativo = bool(flag)
        else:
            self._interativo = bool(interativo)
        self._metadata = {
            "cookies": self._cookies,
            "headers": self._headers,
            "perfil": self.perfil,
        }
        self._url_base_join = f"{self.url_base}/"

        log.debug(
            "Cliente HTTP inicializado",
            perfil=self.perfil,
            base=self.url_base,
            total_cookies=len(self._cookies),
            palavras_erro=len(self._palavras_erro),
            interativo=self._interativo,
        )

    def _notificar_interrupcao(self, mensagem: str) -> None:
        """Reproduz um aviso auditivo/visual quando o modo interativo estiver ativo."""

        if not self._interativo:
            return
        try:
            beep_input(mensagem, False)
        except Exception as exc:  # pragma: no cover - depende do ambiente grafico
            log.aviso("Nao foi possivel emitir alerta interativo", detalhe=str(exc))

    def _detectar_palavras_erro(self, resposta: Response) -> List[str]:
        """Procura palavras-chave de erro dentro do corpo textual da resposta.

        Args:
            resposta: Objeto retornado pela requisição executada.

        Returns:
            Lista de palavras encontradas, vazia quando nenhuma é detectada.
        """

        if not self._palavras_erro:
            return []
        try:
            texto = resposta.text or ""
        except Exception:
            return []
        texto_minusculo = texto.lower()
        return [palavra for palavra in self._palavras_erro if palavra in texto_minusculo]

    @staticmethod
    @request(**_OPCOES_REQUEST)
    def _executar_rota(
        req: Request,
        chamada: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> Response:
        """Executa a rota solicitada utilizando configurações dinâmicas.

        Args:
            req: Objeto de requisição injetado pelo decorator ``@request``.
            chamada: Dicionário com método HTTP, URL final e parâmetros extras.
            metadata: Informações persistidas entre execuções (cookies, headers, perfil).

        Returns:
            Objeto :class:`Response` retornado pelo botasaurus requests.
        """

        cookies_base = dict(metadata.get("cookies") or {})
        headers_base = dict(metadata.get("headers") or {})
        perfil = metadata.get("perfil")
        cookies_extra = chamada.get("cookies") or {}
        headers_extra = chamada.get("headers") or {}
        cookies = {**cookies_base, **cookies_extra} if cookies_base or cookies_extra else {}
        headers = {**headers_base, **headers_extra} if headers_base or headers_extra else {}

        metodo = chamada["metodo"]
        metodo_upper = metodo.upper()
        url = chamada["url"]
        parametros_base = chamada.get("kwargs")
        parametros = dict(parametros_base) if parametros_base else {}

        if headers:
            parametros["headers"] = headers
        if cookies:
            parametros["cookies"] = cookies

        log.debug(
            "Executando request",
            perfil=perfil,
            metodo=metodo_upper,
            url=url,
        )

        operacao = getattr(req, metodo)
        resposta = operacao(url, **parametros)

        log.debug(
            "Request finalizada",
            perfil=perfil,
            status=getattr(resposta, "status_code", None),
        )

        return resposta

    @staticmethod
    def _registrar_erro(
        perfil: str,
        chamada: Mapping[str, Any],
        resposta: Response | None = None,
        erro: Exception | None = None,
        extras: Optional[Mapping[str, Any]] = None,
    ) -> Path:
        """Persiste detalhes das requisições que falharam.

        Args:
            perfil: Identificador do perfil associado ao request.
            chamada: Metadados usados na chamada (URL, método, overrides).
            resposta: Resposta recebida do servidor, quando disponível.
            erro: Exceção levantada durante a execução, se houver.
            extras: Informações adicionais para enriquecer o log.

        Returns:
            Caminho para a pasta contendo os artefatos gravados.
        """

        base = Path.cwd() / "error_logs"
        base.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        destino = base / f"request_{timestamp}"
        contador = 1
        while destino.exists():
            contador += 1
            destino = base / f"request_{timestamp}_{contador}"
        destino.mkdir(parents=True, exist_ok=True)

        detalhes: Dict[str, Any] = {
            "perfil": perfil,
            "metodo": chamada.get("metodo"),
            "url": chamada.get("url"),
            "parametros": chamada.get("kwargs"),
            "headers_personalizados": chamada.get("headers"),
            "cookies_personalizados": chamada.get("cookies"),
        }

        if extras:
            detalhes.update(extras)

        if resposta is not None:
            detalhes.update(
                {
                    "status": getattr(resposta, "status_code", None),
                    "motivo": getattr(resposta, "reason", None),
                    "headers": dict(getattr(resposta, "headers", {}) or {}),
                    "url_final": getattr(resposta, "url", chamada.get("url")),
                }
            )

        if erro is not None:
            detalhes["erro"] = repr(erro)
            detalhes["traceback"] = traceback.format_exc()

        (destino / "detalhes.json").write_text(json.dumps(detalhes, ensure_ascii=False, indent=2), encoding="utf-8")

        if resposta is not None:
            try:
                conteudo_json = resposta.json()
            except Exception:
                conteudo_json = None

            if conteudo_json is not None:
                (destino / "corpo.json").write_text(
                    json.dumps(conteudo_json, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            else:
                (destino / "corpo.txt").write_text(resposta.text or "", encoding="utf-8")

        return destino

    def _resolver_url(self, destino: str) -> str:
        """Normaliza o destino fornecido para uma URL absoluta."""

        if destino.startswith("http://") or destino.startswith("https://"):
            return destino
        return urljoin(self._url_base_join, destino.lstrip("/"))

    def requisicao(self, metodo: str, destino: str, **kwargs) -> Response:
        """Executa a operação HTTP informada reaproveitando sessão autenticada.

        Args:
            metodo: Verbo HTTP a ser executado (``get``, ``post`` ...).
            destino: Caminho absoluto ou relativo a ``url_base``.
            **kwargs: Parâmetros extras passados para a chamada (``params``, ``data`` etc.).

        Returns:
            Resposta retornada pelo cliente botasaurus.

        Raises:
            RuntimeError: Quando a resposta chega com status não OK.
            Exception: Propaga exceções levantadas pelo decorator ``@request``.
        """

        url = self._resolver_url(destino)
        metodo_upper = metodo.upper()
        cookies_personalizados = kwargs.pop("cookies", None)
        headers_personalizados = kwargs.pop("headers", None)
        kwargs, headers_personalizados = inject_request_verification_token(
            metodo,
            kwargs,
            headers_personalizados,
            self._verification_token,
        )
        chamada = {
            "metodo": metodo,
            "url": url,
            "kwargs": kwargs,
            "cookies": cookies_personalizados,
            "headers": headers_personalizados,
        }
        try:
            resposta = self._executar_rota(
                chamada,
                metadata=self._metadata,
                user_agent=self._headers.get("User-Agent"),
            )
        except Exception as erro:
            pasta = self._registrar_erro(self.perfil, chamada, erro=erro)
            log.erro(
                "Erro ao executar request",
                perfil=self.perfil,
                metodo=metodo_upper,
                url=url,
                pasta=str(pasta),
                detalhe=str(erro),
            )
            self._notificar_interrupcao(
                "Request falhou. Analise os logs e pressione Enter para continuar..."
            )
            raise

        if hasattr(resposta, "ok") and not resposta.ok:
            pasta = self._registrar_erro(self.perfil, chamada, resposta=resposta)
            log.erro(
                "Response nao OK",
                perfil=self.perfil,
                metodo=metodo_upper,
                url=url,
                status=resposta.status_code,
                pasta=str(pasta),
            )
            self._notificar_interrupcao(
                "Response nao OK. Verifique os logs e pressione Enter para continuar..."
            )
            raise RuntimeError(f"Request falhou com status {resposta.status_code}")

        palavras_detectadas = self._detectar_palavras_erro(resposta)
        if palavras_detectadas:
            pasta = self._registrar_erro(
                self.perfil,
                chamada,
                resposta=resposta,
                extras={"palavras_detectadas": palavras_detectadas},
            )
            log.erro(
                "Palavras de erro detectadas na resposta",
                perfil=self.perfil,
                metodo=metodo_upper,
                url=url,
                palavras=palavras_detectadas,
                pasta=str(pasta),
            )
            self._notificar_interrupcao(
                "Palavras de erro encontradas. Consulte os logs e pressione Enter para continuar..."
            )
            raise RuntimeError(
                "Request considerado falho por conter palavras de erro: "
                + ", ".join(palavras_detectadas)
            )

        return resposta

    # Alias sem repeticao de logica para os verbos HTTP suportados.
    get = partialmethod(requisicao, "get")
    post = partialmethod(requisicao, "post")
    put = partialmethod(requisicao, "put")
    delete = partialmethod(requisicao, "delete")


__all__ = [
    "SessaoSolicitacoes",
    "GerenciadorSolicitacoesRewards",
    "ClienteSolicitacoesRewards",
]
