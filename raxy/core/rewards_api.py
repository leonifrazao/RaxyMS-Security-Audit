"""Camada de acesso à API do Microsoft Rewards."""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable, Mapping, Optional

from .logging import log
from .session import GerenciadorSolicitacoesRewards


class APIRecompensas:
    """Agrupa chamadas autenticadas e utilitários de parsing da API."""

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
        self._gerenciador = gerenciador
        self._palavras_erro = list(palavras_erro or [])
        self._interativo = interativo
        self._cliente_cache = None

    def _cliente(
        self,
        palavras_erro: Optional[Iterable[str]] = None,
        interativo: Optional[bool] = None,
    ):
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
        cliente = self._cliente(palavras_erro, interativo)
        resposta = cliente.get(
            "/api/getuserinfo?type=1",
            headers=dict(self._CABECALHO_AJAX),
            params=parametros or {"type": "pc"},
        )
        try:
            return resposta.json()
        except Exception as exc:
            log.aviso(
                "Nao foi possivel interpretar JSON de pontos",
                detalhe=str(exc),
            )
            raise

    def obter_recompensas(
        self,
        *,
        parametros: Optional[Mapping[str, str]] = None,
        palavras_erro: Optional[Iterable[str]] = None,
        interativo: Optional[bool] = None,
    ) -> Mapping:
        cliente = self._cliente(palavras_erro, interativo)
        resposta = cliente.get(
            "/api/redeem/getallrewards",
            headers={"Accept": "application/json, text/plain, */*"},
            params=parametros or {},
        )
        try:
            return resposta.json()
        except Exception as exc:
            log.aviso(
                "Nao foi possivel interpretar JSON de recompensas",
                detalhe=str(exc),
            )
            raise

    @staticmethod
    def extrair_pontos_disponiveis(dados: Mapping[str, Any]) -> Optional[int]:
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
                if atual:
                    total += APIRecompensas._contar_recompensas_iter(atual)
                fila.extend(atual)
                continue

            if isinstance(atual, Mapping):
                candidatos = atual.get("catalogItems") or atual.get("items")
                if isinstance(candidatos, list):
                    total += APIRecompensas._contar_recompensas_iter(candidatos)
                fila.extend(atual.values())

        return total or None

    @staticmethod
    def _contar_recompensas_iter(itens: Iterable[Any]) -> int:
        contador = 0
        for item in itens:
            if isinstance(item, Mapping) and APIRecompensas._parece_recompensa(item):
                contador += 1
        return contador

    @staticmethod
    def _converter_para_int(valor: Any) -> Optional[int]:
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
        if not isinstance(item, Mapping):
            return False
        valor = item.get("price")
        if isinstance(valor, (int, float)):
            return True
        if isinstance(valor, str) and valor.replace(".", "", 1).isdigit():
            return True
        return False


__all__ = ["APIRecompensas"]
