"""Testes da API de recompensas focados em requests especificos."""

from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raxy.api.rewards_api import APIRecompensas  # noqa: E402  pylint: disable=wrong-import-position
from raxy.services.session_service import ParametrosManualSolicitacao  # noqa: E402  pylint: disable=wrong-import-position


class _GerenciadorStub:
    """Stub minimo do gerenciador de solicitacoes para os testes."""

    def __init__(self, parametros: ParametrosManualSolicitacao, token: str | None = None) -> None:
        self._parametros = parametros
        self.driver = None
        self._dados_sessao = SimpleNamespace(request_verification_token=token) if token else None

    def parametros_manuais(self, **_: object) -> ParametrosManualSolicitacao:
        return self._parametros

    @property
    def dados_sessao(self) -> SimpleNamespace | None:
        return self._dados_sessao


class _RespostaFalsa:
    """Resposta HTTP simplificada para simular sucesso."""

    ok = True
    status_code = 200

    def json(self) -> dict[str, object]:
        return {"success": True}


class TestAPIRecompensasRequests(unittest.TestCase):
    """Cenários para validar requests customizados na execucao de tarefas."""

    def _criar_parametros(self) -> ParametrosManualSolicitacao:
        return ParametrosManualSolicitacao(
            perfil="perfil",
            url_base="https://rewards.bing.com",
            user_agent="UA",
            headers={},
            cookies={},
            verification_token=None,
            palavras_erro=(),
            interativo=False,
        )

    @patch("raxy.api.rewards_api.TemplateRequester")
    def test_urlreward_utiliza_destino_normalizado(self, mock_template) -> None:
        """Garante que promos normais com ``url`` preencham ``destinationUrl``."""

        parametros = self._criar_parametros()
        api = APIRecompensas(_GerenciadorStub(parametros, token="TOKEN"))
        destino = "https://exemplo.com/recompensa"
        dados = {
            "more_promotions": [
                {
                    "id": "promo-1",
                    "hash": "hash-1",
                    "type": "urlreward",
                    "complete": False,
                    "url": destino,
                }
            ]
        }

        mock_template.return_value.executar.return_value = ({}, _RespostaFalsa())

        resumo = api.executar_tarefas(dados)

        self.assertEqual(resumo["executadas"], 1)
        mock_template.return_value.executar.assert_called_once()
        args, kwargs = mock_template.return_value.executar.call_args
        self.assertEqual(args[0], api._TEMPLATE_EXECUTAR_TAREFA)
        data_extra = kwargs["data_extra"]
        self.assertFalse(kwargs["bypass_request_token"])
        self.assertEqual(data_extra["destinationUrl"], destino)
        self.assertEqual(data_extra["type"], "urlreward")
        self.assertEqual(data_extra["id"], "promo-1")
        self.assertEqual(data_extra["hash"], "hash-1")

    @patch("raxy.api.rewards_api.TemplateRequester")
    def test_urlreward_usa_destino_dos_atributos(self, mock_template) -> None:
        """Confirma que o destino presente em ``attributes`` e aproveitado."""

        parametros = self._criar_parametros()
        api = APIRecompensas(_GerenciadorStub(parametros, token="TOKEN"))
        destino = "https://exemplo.com/atributo"
        dados = {
            "dashboard": {
                "dailySetPromotions": {
                    "2024-09-19": [
                        {
                            "name": "promo-atributo",
                            "hash": "hash-atributo",
                            "complete": False,
                            "promotionType": "urlreward",
                            "attributes": {
                                "destination": destino,
                                "form": "FORM-VALUE",
                            },
                        }
                    ]
                }
            }
        }

        mock_template.return_value.executar.return_value = ({}, _RespostaFalsa())

        resumo = api.executar_tarefas(dados)

        self.assertEqual(resumo["executadas"], 1)
        mock_template.return_value.executar.assert_called_once()
        data_extra = mock_template.return_value.executar.call_args.kwargs["data_extra"]
        self.assertFalse(mock_template.return_value.executar.call_args.kwargs["bypass_request_token"])
        self.assertEqual(data_extra["destinationUrl"], destino)
        self.assertEqual(data_extra["type"], "urlreward")
        self.assertEqual(data_extra["form"], "FORM-VALUE")
        self.assertEqual(data_extra["id"], "promo-atributo")
        self.assertEqual(data_extra["hash"], "hash-atributo")

    def test_blueprint_execucao_basica(self) -> None:
        """Valida que o endpoint Flask integra com o executor de templates."""

        parametros = self._criar_parametros()

        class _RequesterStub:
            calls: list[dict[str, object]] = []

            def __init__(self, gerenciador) -> None:  # pragma: no cover - init simples
                self._gerenciador = gerenciador

            def executar(
                self,
                template: str,
                *,
                data_extra: dict[str, object],
                bypass_request_token: bool = False,
            ) -> tuple[dict[str, object], object | None]:
                registro = {
                    "template": template,
                    "data_extra": dict(data_extra),
                    "bypass": bypass_request_token,
                }
                _RequesterStub.calls.append(registro)
                return {}, None

        _RequesterStub.calls.clear()

        api = APIRecompensas(_GerenciadorStub(parametros), requester_cls=_RequesterStub)
        app = Flask(__name__)
        app.register_blueprint(api.blueprint, url_prefix="/api")

        payload = {
            "more_promotions": [
                {
                    "id": "promo-1",
                    "hash": "hash-1",
                    "type": "urlreward",
                    "complete": False,
                    "url": "https://exemplo.com/promo",
                }
            ]
        }

        resposta = app.test_client().post("/api/rewards/tasks", json=payload)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), {"executadas": 1, "ignoradas": 0})
        self.assertEqual(len(_RequesterStub.calls), 1)
        self.assertEqual(_RequesterStub.calls[0]["template"], api._TEMPLATE_EXECUTAR_TAREFA)
        self.assertFalse(_RequesterStub.calls[0]["bypass"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
