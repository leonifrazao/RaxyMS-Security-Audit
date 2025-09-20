"""Testes da API de recompensas focados em requests especificos."""

from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raxy.core.rewards_api import APIRecompensas  # noqa: E402  pylint: disable=wrong-import-position
from raxy.core.session import ParametrosManualSolicitacao  # noqa: E402  pylint: disable=wrong-import-position


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

    @patch("raxy.core.rewards_api.TemplateRequester")
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
        self.assertEqual(data_extra["destinationUrl"], destino)
        self.assertEqual(data_extra["type"], "urlreward")
        self.assertEqual(data_extra["id"], "promo-1")
        self.assertEqual(data_extra["hash"], "hash-1")

    @patch("raxy.core.rewards_api.TemplateRequester")
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
        self.assertEqual(data_extra["destinationUrl"], destino)
        self.assertEqual(data_extra["type"], "urlreward")
        self.assertEqual(data_extra["form"], "FORM-VALUE")
        self.assertEqual(data_extra["id"], "promo-atributo")
        self.assertEqual(data_extra["hash"], "hash-atributo")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
