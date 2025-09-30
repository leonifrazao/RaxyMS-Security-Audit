"""API de alto nível para execução de tarefas Microsoft Rewards."""

from __future__ import annotations

from typing import Iterable, Mapping, MutableMapping

from interfaces.services import IAPIRecompensasService, IGerenciadorSolicitacoesService


class TemplateRequester:
    """Abstrai o envio de templates JSON utilizando a sessão autenticada."""

    def __init__(self, gerenciador: IGerenciadorSolicitacoesService) -> None:
        self._gerenciador = gerenciador

    def executar(
        self,
        template: str,
        *,
        data_extra: Mapping[str, object] | None = None,
        bypass_request_token: bool = False,
    ) -> tuple[Mapping[str, object], object | None]:
        """Executa o template informado com dados adicionais.

        A implementação padrão não realiza requisição real; ela retorna um
        dicionário com os dados reunidos, permitindo fácil substituição por
        mocks em testes e customizações.
        """

        parametros = self._gerenciador.parametros_manuais(interativo=False)
        payload: MutableMapping[str, object] = {
            "template": template,
            "perfil": parametros.perfil,
            "url_base": parametros.url_base,
            "headers": dict(parametros.headers),
            "cookies": dict(parametros.cookies),
            "user_agent": parametros.user_agent,
            "bypass_request_token": bypass_request_token,
        }
        if parametros.verification_token:
            payload["verification_token"] = parametros.verification_token
        if data_extra:
            payload["extra"] = dict(data_extra)
        return payload, None


class APIRecompensas(IAPIRecompensasService):
    """Processa dados do Rewards e aciona execução de tarefas."""

    _TEMPLATE_EXECUTAR_TAREFA = "pegar_recompensa_rewards.json"

    def __init__(
        self,
        gerenciador: IGerenciadorSolicitacoesService,
        *,
        requester_cls: type[TemplateRequester] = TemplateRequester,
    ) -> None:
        self._gerenciador = gerenciador
        self._requester_cls = requester_cls

    def executar_tarefas(
        self,
        dados: Mapping[str, object],
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, int]:
        requester = self._requester_cls(self._gerenciador)
        resumo = {"executadas": 0, "ignoradas": 0}

        for promocao in self._iter_promocoes(dados):
            if promocao.get("complete"):
                resumo["ignoradas"] += 1
                continue

            extras = self._montar_payload(promocao)
            requester.executar(
                self._TEMPLATE_EXECUTAR_TAREFA,
                data_extra=extras,
                bypass_request_token=bypass_request_token,
            )
            resumo["executadas"] += 1

        return resumo

    def _iter_promocoes(self, dados: Mapping[str, object]) -> Iterable[Mapping[str, object]]:
        more_promotions = dados.get("more_promotions")
        if isinstance(more_promotions, list):
            for item in more_promotions:
                if isinstance(item, Mapping):
                    yield item

        dashboard = dados.get("dashboard")
        if isinstance(dashboard, Mapping):
            daily_sets = dashboard.get("dailySetPromotions")
            if isinstance(daily_sets, Mapping):
                for _, promocoes in daily_sets.items():
                    if isinstance(promocoes, list):
                        for promo in promocoes:
                            if isinstance(promo, Mapping):
                                yield promo

    def _montar_payload(self, promocao: Mapping[str, object]) -> Mapping[str, object]:
        tipo = (promocao.get("type") or promocao.get("promotionType") or "").strip()
        identificador = promocao.get("id") or promocao.get("name") or ""
        hash_promocao = promocao.get("hash")

        destino = promocao.get("url")
        atributos = promocao.get("attributes")
        if (not destino or not isinstance(destino, str)) and isinstance(atributos, Mapping):
            destino = atributos.get("destination")

        extras: MutableMapping[str, object] = {
            "type": tipo,
        }
        if identificador:
            extras["id"] = identificador
        if hash_promocao:
            extras["hash"] = hash_promocao
        if destino:
            extras["destinationUrl"] = destino
        if isinstance(atributos, Mapping):
            extras.update({k: v for k, v in atributos.items() if k != "destination"})

        return extras

    @staticmethod
    def _parse_bool(value: str | None) -> bool:
        if value is None:
            return False
        valor_normalizado = value.strip().lower()
        return valor_normalizado in {"1", "true", "t", "yes", "y", "on"}


__all__ = ["APIRecompensas", "TemplateRequester"]
