"""Fluxos relacionados a navegacao e interacoes com o Rewards."""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable, Mapping, Optional

from botasaurus.browser import browser, Driver

from .config import BROWSER_KWARGS, REWARDS_BASE_URL
from .solicitacoes import GerenciadorSolicitacoesRewards
from .logging import log


class NavegadorRecompensas:
    """Encapsula operacoes de navegacao na pagina do Bing Rewards."""

    _CONFIG_PADRAO = {**BROWSER_KWARGS, "reuse_driver": False}

    @classmethod
    def abrir_pagina(
        cls,
        *,
        reuse_driver: Optional[bool] = None,
        **kwargs,
    ):
        """Abre a pagina principal do Microsoft Rewards com configuracao flexivel.

        A flag ``reuse_driver`` pode ser sobrescrita por chamada, permitindo que
        fluxos paralelos usem instancias isoladas do navegador sem compartilhar
        estado global.
        """

        configuracao = dict(cls._CONFIG_PADRAO)
        if reuse_driver is not None:
            configuracao["reuse_driver"] = reuse_driver

        @browser(**configuracao)
        def _abrir(driver: Driver, dados=None):
            """Função interna executada pelo botasaurus para abrir a página."""

            driver.enable_human_mode()
            driver.google_get(REWARDS_BASE_URL)
            html = getattr(driver, "page_source", "") or ""
            if "Sign in" in html or "Entrar" in html:
                log.aviso(
                    "Parece que voce nao esta logado no Rewards",
                    detalhe="Acesse https://rewards.microsoft.com/ e entre com sua conta Microsoft",
                )
            driver.prompt()

        return _abrir(**kwargs)


class APIRecompensas:
    """Agrupa chamadas de API do Rewards reutilizando um gerenciador existente."""

    _CABECALHO_AJAX: Mapping[str, str] = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    def __init__(
        self,
        gerenciador: GerenciadorSolicitacoesRewards,
        *,
        palavras_erro: Optional[Iterable[str]] = None,
        interativo: Optional[bool] = None,
    ) -> None:
        """Inicializa o wrapper reutilizando um gerenciador de solicitações.

        Args:
            gerenciador: Instância capturada após o login contendo cookies e
                cabeçalhos autenticados.
            palavras_erro: Coleção de palavras que sinalizam falhas nas
                respostas HTTP.
            interativo: Define se prompts do botasaurus devem ser emitidos.
        """

        self._gerenciador = gerenciador
        self._palavras_erro = list(palavras_erro or [])
        self._interativo = interativo
        self._cliente_cache = None

    def _cliente(
        self,
        palavras_erro: Optional[Iterable[str]] = None,
        interativo: Optional[bool] = None,
    ):
        """Retorna um cliente HTTP autenticado reutilizando caches internos.

        Args:
            palavras_erro: Lista a ser aplicada antes da criação do cliente.
            interativo: Override temporário para o modo interativo.

        Returns:
            Cliente retornado por ``GerenciadorSolicitacoesRewards.criar_cliente``.
        """

        if palavras_erro is not None:
            self._palavras_erro = list(palavras_erro or [])
            self._cliente_cache = None
        if interativo is not None and interativo != self._interativo:
            self._interativo = interativo
            self._cliente_cache = None
        if self._cliente_cache is None:
            self._cliente_cache = self._gerenciador.criar_cliente(
                palavras_erro=self._palavras_erro,
                interativo=self._interativo,
            )
        return self._cliente_cache

    def obter_pontos(
        self,
        *,
        parametros: Optional[Mapping[str, str]] = None,
        palavras_erro: Optional[Iterable[str]] = None,
        interativo: Optional[bool] = None,
    ) -> Mapping:
        """Consulta o consolidado de pontos do Rewards.

        Args:
            parametros: Query string adicional para a rota.
            palavras_erro: Lista temporária de palavras de erro.
            interativo: Ajuste temporário de interatividade.

        Returns:
            Mapeamento com o corpo JSON retornado pela API.

        Raises:
            Exception: Propaga qualquer erro de conversão JSON.
        """

        cliente = self._cliente(palavras_erro, interativo)
        resposta = cliente.get(
            "/api/getuserinfo?type=1",
            headers=dict(self._CABECALHO_AJAX),
            params=parametros or {"type": "pc"},
        )
        try:
            dados = resposta.json()
        except Exception as exc:
            log.aviso(
                "Nao foi possivel interpretar JSON de pontos",
                detalhe=str(exc),
            )
            raise
        return dados

    def obter_recompensas(
        self,
        *,
        parametros: Optional[Mapping[str, str]] = None,
        palavras_erro: Optional[Iterable[str]] = None,
        interativo: Optional[bool] = None,
    ) -> Mapping:
        """Recupera a lista de recompensas disponíveis.

        Args:
            parametros: Query string adicional para a rota.
            palavras_erro: Lista temporária de palavras de erro.
            interativo: Ajuste temporário de interatividade.

        Returns:
            Mapeamento com o corpo JSON de recompensas.

        Raises:
            Exception: Propaga erros de conversão JSON.
        """

        cliente = self._cliente(palavras_erro, interativo)
        resposta = cliente.get(
            "/api/redeem/getallrewards",
            headers={"Accept": "application/json, text/plain, */*"},
            params=parametros or {},
        )
        try:
            dados = resposta.json()
        except Exception as exc:
            log.aviso(
                "Nao foi possivel interpretar JSON de recompensas",
                detalhe=str(exc),
            )
            raise
        return dados

    @staticmethod
    def extrair_pontos_disponiveis(dados: Mapping[str, Any]) -> Optional[int]:
        """Busca o valor de ``availablePoints`` em qualquer nível do JSON.

        Args:
            dados: Corpo JSON retornado pela API de pontos.

        Returns:
            Valor inteiro quando encontrado; ``None`` caso ausente.
        """

        fila = deque([dados])
        visitados: set[int] = set()
        while fila:
            atual = fila.popleft()
            identificador = id(atual)
            if identificador in visitados:
                continue
            visitados.add(identificador)

            if isinstance(atual, Mapping):
                if "availablePoints" in atual:
                    return APIRecompensas._converter_para_int(atual.get("availablePoints"))
                fila.extend(atual.values())
            elif isinstance(atual, list):
                fila.extend(atual)

        return None

    @staticmethod
    def contar_recompensas(dados: Any) -> Optional[int]:
        """Conta recompensas detectando listas relevantes em estruturas aninhadas.

        Args:
            dados: Estrutura JSON retornada pela API de recompensas.

        Returns:
            Quantidade total de itens identificados como recompensas ou ``None``
            quando nenhuma lista válida é encontrada.
        """

        fila = deque([dados])
        visitados: set[int] = set()
        total = 0

        while fila:
            atual = fila.popleft()
            identificador = id(atual)
            if identificador in visitados:
                continue
            visitados.add(identificador)

            if isinstance(atual, list):
                if atual and all(isinstance(item, Mapping) for item in atual):
                    relevantes = [
                        item for item in atual if APIRecompensas._parece_recompensa(item)
                    ]
                    if relevantes:
                        total += len(relevantes)
                fila.extend(atual)
                continue

            if isinstance(atual, Mapping):
                candidatos = atual.get("catalogItems") or atual.get("items")
                if isinstance(candidatos, list):
                    relevantes = [
                        item for item in candidatos if APIRecompensas._parece_recompensa(item)
                    ]
                    if relevantes:
                        total += len(relevantes)
                fila.extend(atual.values())

        return total or None

    @staticmethod
    def _converter_para_int(valor: Any) -> Optional[int]:
        """Converte valores numéricos ou strings numéricas para inteiro.

        Args:
            valor: Objeto retornado pelo JSON (int, float, str, etc.).

        Returns:
            Inteiro absoluto quando possível; ``None`` quando a conversão falha.
        """

        if isinstance(valor, (int, float)):
            return int(valor)
        if isinstance(valor, str) and valor.strip():
            try:
                return int(float(valor))
            except ValueError:
                return None
        return None

    @staticmethod
    def _parece_recompensa(item: Mapping[str, Any]) -> bool:
        """Verifica heurísticamente se um item do JSON representa recompensa.

        Args:
            item: Dicionário potencialmente descrevendo uma recompensa.

        Returns:
            ``True`` quando um campo ``price`` numérico é encontrado; caso
            contrário ``False``.
        """

        if not isinstance(item, Mapping):
            return False
        valor = item.get("price")
        if isinstance(valor, (int, float)):
            return True
        if isinstance(valor, str) and valor.replace(".", "", 1).isdigit():
            return True
        return False


__all__ = ["NavegadorRecompensas", "APIRecompensas"]
