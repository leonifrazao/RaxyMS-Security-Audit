"""Testes do blueprint Flask em ``RewardsDataAPI``."""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch

from flask import Flask

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raxy.api.rewards_data_api import RewardsDataAPI  # noqa: E402  pylint: disable=wrong-import-position


class TestRewardsDataBlueprint(unittest.TestCase):
    """Cenários cobrindo o blueprint HTTP do RewardsDataAPI."""

    @staticmethod
    def _create_app(api: RewardsDataAPI) -> Flask:
        app = Flask(__name__)
        app.register_blueprint(api.blueprint, url_prefix="/api")
        return app

    def test_points_endpoint_sem_provider(self) -> None:
        api = RewardsDataAPI()
        client = self._create_app(api).test_client()

        resposta = client.get("/api/rewards/data/points")

        self.assertEqual(resposta.status_code, 503)
        dados = resposta.get_json()
        self.assertIsInstance(dados, dict)
        self.assertIn("error", dados)

    def test_points_endpoint_com_provider(self) -> None:
        api = RewardsDataAPI()
        sentinel = object()
        api.set_request_provider(lambda: sentinel)
        client = self._create_app(api).test_client()

        with patch.object(api, "obter_pontos", return_value=777) as mock_obter:
            resposta = client.get("/api/rewards/data/points?bypass_request_token=true")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), {"points": 777})
        mock_obter.assert_called_once_with(sentinel, bypass_request_token=True)

    def test_promotions_endpoint_com_provider(self) -> None:
        api = RewardsDataAPI()
        sentinel = object()
        api.set_request_provider(lambda: sentinel)
        client = self._create_app(api).test_client()

        retorno = {"daily_sets": [], "more_promotions": [1, 2, 3]}
        with patch.object(api, "obter_recompensas", return_value=retorno) as mock_obter:
            resposta = client.get("/api/rewards/data/promotions")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), retorno)
        mock_obter.assert_called_once_with(sentinel, bypass_request_token=False)

    def test_execute_endpoint_com_provider(self) -> None:
        api = RewardsDataAPI()
        sentinel = object()
        api.set_request_provider(lambda: sentinel)
        client = self._create_app(api).test_client()

        retorno = {"daily_sets": [], "more_promotions": []}
        with patch.object(api, "pegar_recompensas", return_value=retorno) as mock_pegar:
            resposta = client.post("/api/rewards/data/promotions/execute?bypass_request_token=1")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), retorno)
        mock_pegar.assert_called_once_with(sentinel, bypass_request_token=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
