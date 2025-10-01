from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    # Assume que BaseRequest está localizado em services.session_service
    # conforme a estrutura dos exemplos fornecidos.
    from services.session_service import BaseRequest

# Define o diretório de requests baseado na localização deste arquivo.
# Ex: se o arquivo está em /src/api/rewards_tasks.py,
# o diretório de requests será /src/requests/
REQUESTS_DIR = Path(__file__).resolve().parents[1] / "requests"


class RewardsTasksAPI:
    """
    Serviço para executar tarefas genéricas do Microsoft Rewards
    baseadas em templates JSON parametrizáveis.
    """

    @staticmethod
    def _substituir_placeholders(template_obj: Any, valores: Mapping[str, Any]) -> Any:
        """
        Percorre recursivamente um objeto (dicionário ou lista) e substitui
        valores que são a string '{definir}' pelo valor correspondente
        no dicionário 'valores', usando a chave do objeto como referência.

        Args:
            template_obj: O objeto (dict, list, str, etc.) a ser processado.
            valores: Um dicionário contendo os valores para substituição.

        Returns:
            O objeto com os placeholders substituídos.

        Raises:
            KeyError: Se um valor para um placeholder '{definir}' não for fornecido.
        """
        if isinstance(template_obj, dict):
            novo_dict = {}
            for key, value in template_obj.items():
                if isinstance(value, str) and value == "{definir}":
                    if key in valores:
                        novo_dict[key] = valores[key]
                    else:
                        raise KeyError(
                            f"O valor para o placeholder da chave '{key}' não foi fornecido no dicionário de valores."
                        )
                else:
                    # Continua a recursão para objetos aninhados
                    novo_dict[key] = RewardsTasksAPI._substituir_placeholders(value, valores)
            return novo_dict
        elif isinstance(template_obj, list):
            # Aplica a recursão para cada item da lista
            return [RewardsTasksAPI._substituir_placeholders(item, valores) for item in template_obj]
        else:
            # Retorna o valor como está se não for um dict ou list (ex: str, int)
            return template_obj

    def executar_tarefa(
        self,
        base: BaseRequest,
        nome_template: str,
        valores_para_preencher: Mapping[str, Any],
        *,
        bypass_request_token: bool = False,
    ) -> Any:
        """
        Executa uma request HTTP baseada em um template JSON, preenchendo
        os campos marcados com '{definir}'.

        Args:
            base: A instância de BaseRequest para executar a chamada HTTP.
            nome_template: O nome do arquivo JSON do template na pasta 'requests'.
            valores_para_preencher: Um dicionário com os valores para substituir
                                    os placeholders. A chave do dicionário deve
                                    corresponder à chave no JSON cujo valor é '{definir}'.
            bypass_request_token: Se True, não injeta o token anti-falsificação
                                  automaticamente pela classe BaseRequest.

        Returns:
            O corpo da resposta da request, decodificado como JSON se possível,
            caso contrário, o texto puro.

        Raises:
            FileNotFoundError: Se o arquivo de template não for encontrado.
            KeyError: Se um valor necessário para um placeholder não for fornecido.
            RuntimeError: Se a request HTTP falhar (ex: status code não for 2xx).
        """
        caminho_template = REQUESTS_DIR / nome_template
        if not caminho_template.is_file():
            raise FileNotFoundError(f"O template '{nome_template}' não foi encontrado em '{caminho_template}'.")

        with open(caminho_template, "r", encoding="utf-8") as f:
            template_original = json.load(f)

        # Usa deepcopy para garantir que o template original não seja modificado em memória
        template_copiado = deepcopy(template_original)

        # Preenche os placeholders com os valores fornecidos
        template_final = self._substituir_placeholders(template_copiado, valores_para_preencher)

        # Monta e envia a request usando a infraestrutura existente de BaseRequest
        argumentos = base._montar(template_final, bypass_request_token=bypass_request_token)
        resposta = base._enviar(argumentos)

        if not getattr(resposta, "ok", False):
            status = getattr(resposta, 'status_code', 'N/A')
            texto_resposta = getattr(resposta, 'text', '[sem corpo na resposta]')
            raise RuntimeError(
                f"A request para o template '{nome_template}' falhou com status {status}. "
                f"Resposta: {texto_resposta}"
            )

        try:
            # Tenta retornar o JSON, se não for possível, retorna o texto puro
            return resposta.json()
        except json.JSONDecodeError:
            return resposta.text


__all__ = ["RewardsTasksAPI"]