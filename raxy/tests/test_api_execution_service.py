"""Testes unitarios do modulo ``services.api_execution_service``."""

from __future__ import annotations

import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

wonder_module = types.ModuleType("wonderwords")


class _RandomWordStub:
    def word(self, **_: object) -> str:  # pragma: no cover - comportamento trivial
        return "stub"


wonder_module.RandomWord = _RandomWordStub
sys.modules.setdefault("wonderwords", wonder_module)

from raxy.services.api_execution_service import (  # noqa: E402  pylint: disable=wrong-import-position
    BuscaPayloadConfig,
    RewardsAPIsService,
)


class _BaseRequestStub:
    """Simula um ``BaseRequest`` sem comportamento adicional."""


class _GerenciadorStub:
    """Gerenciador minimo apenas para satisfazer a interface."""

    dados_sessao = None

    def parametros_manuais(self, **_: object):  # pragma: no cover - nao utilizado
        raise AssertionError("parametros_manuais nao deveria ser chamado nos testes")


class _BingAPIStub:
    """Stub controlando as chamadas de pesquisa."""

    def __init__(self) -> None:
        self.calls: list[tuple[object | None, str | None]] = []
        self._auto_idx = 0

    def pesquisar(self, *, base: object | None = None, query: str | None = None) -> dict[str, object]:
        self.calls.append((base, query))
        if query is None:
            query = f"auto-{self._auto_idx}"
            self._auto_idx += 1
        return {"query": query, "request": {"url": f"https://example.com?q={query}"}}


class _RewardsDataStub:
    """Stub da camada de dados do Rewards."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object, bool]] = []
        self.promocoes = {"daily_sets": [1], "more_promotions": [2]}
        self.pontos = 777

    def obter_pontos(self, base: object, *, bypass_request_token: bool = False) -> int:
        self.calls.append(("pontos", base, bypass_request_token))
        return self.pontos

    def obter_recompensas(self, base: object, *, bypass_request_token: bool = False) -> dict[str, object]:
        self.calls.append(("recompensas", base, bypass_request_token))
        return dict(self.promocoes)


class _APIRecompensasStub:
    """Stub que armazena os dados recebidos na execucao das tarefas."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, bool]] = []
        self.resumo = {"executadas": 1, "ignoradas": 2}

    def executar_tarefas(self, dados: object, *, bypass_request_token: bool = False) -> dict[str, int]:
        self.calls.append((dados, bypass_request_token))
        return dict(self.resumo)


class RewardsAPIsServiceTest(unittest.TestCase):
    """Cenarios cobrindo as operacoes principais do servico."""

    def setUp(self) -> None:
        self.base = _BaseRequestStub()
        self.gerenciador = _GerenciadorStub()
        self.rewards_data = _RewardsDataStub()
        self.api_stub = _APIRecompensasStub()
        self.bing_stub = _BingAPIStub()

        def bing_factory(provider):
            self.assertIs(provider(), self.base)
            return self.bing_stub

        self.service = RewardsAPIsService(
            request_provider=lambda: self.base,
            gerenciador=self.gerenciador,
            rewards_data=self.rewards_data,
            api_recompensas_factory=lambda _: self.api_stub,
            bing_api_factory=bing_factory,
        )

    def test_executar_pesquisas_respeita_payloads(self) -> None:
        """Cada payload gera o numero correto de chamadas ao Bing."""

        payloads = [
            BuscaPayloadConfig(nome="desktop", quantidade=2, consultas=["consulta-1", None]),
            BuscaPayloadConfig(nome="mobile", quantidade=1),
        ]

        resultados = self.service.executar_pesquisas(payloads)

        self.assertEqual(len(resultados), 3)
        self.assertEqual(len(self.bing_stub.calls), 3)
        # ordem: consulta explicita, consulta None -> auto, payload mobile
        self.assertEqual(self.bing_stub.calls[0][1], "consulta-1")
        self.assertEqual(self.bing_stub.calls[1][1], "auto-0")
        self.assertEqual(self.bing_stub.calls[2][1], "auto-1")
        for base_chamada, _ in self.bing_stub.calls:
            self.assertIs(base_chamada, self.base)

        payloads_retornados = [item.payload for item in resultados]
        self.assertIn("desktop", payloads_retornados)
        self.assertIn("mobile", payloads_retornados)

    def test_obter_pontos_encaminha_para_rewards_data(self) -> None:
        """O metodo delega para ``RewardsDataAPI.obter_pontos`` com o bypass informado."""

        pontos = self.service.obter_pontos(bypass_request_token=True)

        self.assertEqual(pontos, self.rewards_data.pontos)
        self.assertEqual(len(self.rewards_data.calls), 1)
        nome, base, bypass = self.rewards_data.calls[0]
        self.assertEqual(nome, "pontos")
        self.assertIs(base, self.base)
        self.assertTrue(bypass)

    def test_executar_promocoes_reutiliza_dados_quando_informados(self) -> None:
        """Dados de promocoes sao encaminhados diretamente ao executor."""

        dados = {"daily_sets": [], "more_promotions": []}
        resumo = self.service.executar_promocoes(dados, bypass_request_token=True)

        self.assertEqual(resumo, self.api_stub.resumo)
        self.assertEqual(self.api_stub.calls, [(dados, True)])
        self.assertFalse([call for call in self.rewards_data.calls if call[0] == "recompensas"])

    def test_executar_promocoes_coleta_dados_quando_necessario(self) -> None:
        """Sem dados pre-carregados, o servico obtem promocoes automaticamente."""

        resumo = self.service.executar_promocoes(dados=None, bypass_request_token=False)

        self.assertEqual(resumo, self.api_stub.resumo)
        self.assertEqual(len(self.rewards_data.calls), 1)
        nome, base, bypass = self.rewards_data.calls[0]
        self.assertEqual(nome, "recompensas")
        self.assertIs(base, self.base)
        self.assertFalse(bypass)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
