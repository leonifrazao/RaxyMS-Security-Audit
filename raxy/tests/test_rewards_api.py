"""Testes focados nas rotinas de busca do Bing dentro da API do Rewards."""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from raxy.core.rewards_api import APIRecompensas  # noqa: E402  pylint: disable=wrong-import-position
from raxy.core.session import ParametrosManualSolicitacao  # noqa: E402  pylint: disable=wrong-import-position
from raxy.core.logging import log  # noqa: E402  pylint: disable=wrong-import-position


class DummyGerenciador:
    """Stub simples para fornecer parametros manuais à API."""

    def __init__(self, parametros: ParametrosManualSolicitacao) -> None:
        self._parametros = parametros
        self.dados_sessao = None

    def parametros_manuais(self, **kwargs):  # noqa: D401 - interface de stub
        return self._parametros


class TestAPIRecompensasPcSearch(unittest.TestCase):
    """Garante que as rotinas de pesquisa no PC sejam orquestradas corretamente."""

    def _criar_api(self) -> APIRecompensas:
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
        return APIRecompensas(DummyGerenciador(parametros))

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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
