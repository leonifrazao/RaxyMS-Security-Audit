"""Testes focados nas rotinas de busca do Bing dentro da API do Rewards."""

from __future__ import annotations

import pathlib
import sys
import unittest
from typing import Any, Dict
from urllib.parse import urlencode
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import raxy.core.rewards_api as rewards_mod  # noqa: E402  pylint: disable=wrong-import-position
from raxy.core.rewards_api import APIRecompensas  # noqa: E402  pylint: disable=wrong-import-position
from raxy.core.session import ParametrosManualSolicitacao  # noqa: E402  pylint: disable=wrong-import-position
from raxy.core.logging import log  # noqa: E402  pylint: disable=wrong-import-position


class DummyGerenciador:
    """Stub simples para fornecer parametros manuais à API."""

    def __init__(
        self,
        parametros: ParametrosManualSolicitacao,
        *,
        driver: Any | None = None,
    ) -> None:
        self._parametros = parametros
        self.dados_sessao = None
        self.driver = driver

    def parametros_manuais(self, **kwargs):  # noqa: D401 - interface de stub
        return self._parametros


class TestAPIRecompensasPcSearch(unittest.TestCase):
    """Garante que as rotinas de pesquisa no PC sejam orquestradas corretamente."""

    def _criar_api(self, *, driver: Any | None = None) -> APIRecompensas:
        parametros = ParametrosManualSolicitacao(
            perfil="teste",
            url_base="https://rewards.bing.com",
            user_agent="UA",
            headers={"Accept-Language": "pt-BR,pt;q=0.9"},
            cookies={},
            verification_token=None,
            palavras_erro=(),
            interativo=False,
        )
        return APIRecompensas(DummyGerenciador(parametros, driver=driver))

    def test_obter_contadores_pc_filtra_itens_validos(self) -> None:
        """Somente dicionários válidos devem ser retornados pela extração de contadores."""

        dados = {
            "raw_dashboard": {
                "counters": {
                    "pcSearch": [
                        {"name": "um"},
                        "ignorar",
                        {"name": "dois", "attributes": {"progress": "5", "max": "10"}},
                    ]
                }
            }
        }

        contadores = APIRecompensas._obter_contadores_pc(dados)
        self.assertEqual(len(contadores), 2)
        self.assertEqual(contadores[0]["name"], "um")

    def test_obter_contadores_pc_busca_em_user_status(self) -> None:
        """Estruturas novas do dashboard devem ser analisadas para localizar os contadores."""

        dados = {
            "raw_dashboard": {
                "userStatus": {
                    "counters": {
                        "pcSearch": [
                            {"name": "novo"},
                            None,
                        ]
                    }
                }
            }
        }

        contadores = APIRecompensas._obter_contadores_pc(dados)
        self.assertEqual(len(contadores), 1)
        self.assertEqual(contadores[0]["name"], "novo")

    def test_detectar_pontos_por_pesquisa_ler_descricao(self) -> None:
        """O número de pontos por pesquisa deve ser extraído da descrição quando presente."""

        contador = {
            "attributes": {
                "description": "Ganha até 30 pontos por dia, 3 pontos por pesquisa no PC",
            }
        }
        pontos = APIRecompensas._detectar_pontos_por_pesquisa(contador)
        self.assertEqual(pontos, 3)

    def test_executar_pesquisas_pc_sem_pendente(self) -> None:
        """Nenhuma busca deve ser disparada quando progressos e máximos coincidem."""

        api = self._criar_api()
        dados = {
            "raw_dashboard": {
                "counters": {
                    "pcSearch": [
                        {
                            "name": "PC",
                            "attributes": {"progress": "30", "max": "30"},
                        }
                    ]
                }
            }
        }
        resumo = {"executadas": 0, "falhas": 0, "ignoradas": 0, "ja_concluidas": 0, "total": 0}

        with patch.object(APIRecompensas, "_realizar_pesquisas_bing") as mock_exec:
            api._executar_pesquisas_pc(dados, logger=log, resumo=resumo)

        mock_exec.assert_not_called()
        self.assertNotIn("pesquisas_pc_previstas", resumo)

    def test_executar_pesquisas_pc_dispara_execucao(self) -> None:
        """Quando há pontos pendentes a API deve acionar as buscas e atualizar o resumo."""

        api = self._criar_api()
        dados = {
            "raw_dashboard": {
                "counters": {
                    "pcSearch": [
                        {
                            "name": "PC",
                            "attributes": {
                                "progress": "6",
                                "max": "15",
                                "description": "Ganhe pontos – 3 pontos por pesquisa",
                            },
                        }
                    ]
                }
            }
        }
        resumo = {"executadas": 0, "falhas": 0, "ignoradas": 0, "ja_concluidas": 0, "total": 0}

        with patch.object(
            APIRecompensas,
            "_realizar_pesquisas_bing",
            return_value=(2, 1, 3),
        ) as mock_exec:
            api._executar_pesquisas_pc(dados, logger=log, resumo=resumo)

        mock_exec.assert_called_once()
        chamada = mock_exec.call_args.kwargs
        self.assertEqual(chamada["quantidade"], 3)
        self.assertEqual(resumo.get("pesquisas_pc_previstas"), 3)
        self.assertEqual(resumo.get("pesquisas_pc_executadas"), 2)
        self.assertEqual(resumo.get("pesquisas_pc_falhas"), 1)
        self.assertEqual(resumo.get("pesquisas_pc_restantes_estimado"), 3)

    def test_executar_busca_bing_utiliza_driver_requests(self) -> None:
        """A rotina de busca deve usar driver.requests e sincronizar cookies corretamente."""

        class DummyCookieJar(dict):
            def get_dict(self):
                return dict(self)

        class DummyResponse:
            def __init__(
                self,
                url: str,
                *,
                cookies: Dict[str, str] | None = None,
                ok: bool = True,
                json_data: Dict[str, Any] | None = None,
            ) -> None:
                self.url = url
                self.ok = ok
                self.status_code = 200
                self._json_data = json_data
                self.cookies = DummyCookieJar(cookies or {})
                self.text = "<html></html>"

            def json(self):
                if self._json_data is None:
                    raise ValueError("sem dados")
                return self._json_data

        class DummyRequests:
            def __init__(self) -> None:
                self.get_calls: list[tuple[str, Dict[str, Any]]] = []
                self.post_calls: list[tuple[str, Dict[str, Any]]] = []

            def get(self, url: str, **kwargs: Any) -> DummyResponse:
                self.get_calls.append((url, kwargs))
                params = kwargs.get("params") or {}
                consulta_url = f"{url}?{urlencode(params)}" if params else url
                return DummyResponse(consulta_url, cookies={"SRCHHPGUSR": "lang=pt"})

            def post(self, url: str, **kwargs: Any) -> DummyResponse:
                self.post_calls.append((url, kwargs))
                return DummyResponse(url, cookies={"MSPTC": "1"}, json_data={"success": True})

        class DummyDriver:
            def __init__(self, requisicoes: DummyRequests) -> None:
                self.requests = requisicoes
                self.page_source = "<html>Usuario logado</html>"
                self.current_url = ""
                self.called_urls: list[str] = []
                self._cookies: Dict[str, str] = {"SRCHHPGUSR": "lang=pt"}

            def google_get(self, url: str) -> None:
                self.called_urls.append(url)
                self.current_url = url
                if "search" in url:
                    self.current_url = f"{url}&via=browser"
                    self._cookies["BINGAUTH"] = "1"

            def short_random_sleep(self) -> None:
                return None

            def get_cookies_dict(self) -> Dict[str, str]:
                return dict(self._cookies)

        requisicoes = DummyRequests()
        driver = DummyDriver(requisicoes)
        api = self._criar_api(driver=driver)
        parametros = api.obter_parametros()
        cookies: Dict[str, str] = {}
        accept_language = parametros.headers.get("Accept-Language", "pt-BR,pt;q=0.9")

        api._preparar_bing_para_pesquisa(driver, log)
        api._sincronizar_cookies_navegador(cookies, driver, log, "teste")
        sucesso = api._executar_busca_bing(
            consulta="consulta automatizada",
            parametros=parametros,
            cookies=cookies,
            accept_language=accept_language,
            logger=log,
            driver=driver,
            requisicoes=requisicoes,
            preparado=True,
        )

        self.assertTrue(sucesso)
        self.assertEqual(len(requisicoes.get_calls), 1)
        self.assertEqual(len(requisicoes.post_calls), 1)
        get_kwargs = requisicoes.get_calls[0][1]
        self.assertEqual(get_kwargs["headers"]["Accept-Language"], "pt-BR,pt;q=0.9")
        self.assertIn("SRCHHPGUSR", cookies)
        self.assertIn("MSPTC", cookies)
        self.assertIn("BINGAUTH", cookies)
        self.assertGreaterEqual(len(driver.called_urls), 2)
        self.assertEqual(driver.called_urls[0], rewards_mod._BING_HOME_URL)
        self.assertTrue(driver.called_urls[1].startswith(rewards_mod._BING_SEARCH_URL))
        post_payload = requisicoes.post_calls[0][1]
        self.assertEqual(post_payload["data"]["url"], driver.current_url)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
