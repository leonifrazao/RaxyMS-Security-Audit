"""Serviços de orquestração para processamento em lote das contas."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional

from ..core import (
    APIRecompensas,
    AutenticadorRewards,
    GerenciadorPerfil,
    GerenciadorSolicitacoesRewards,
    NavegadorRecompensas,
)
from ..core.accounts import Conta, carregar_contas
from ..core.config import DEFAULT_ACTIONS, ExecutorConfig
from ..core.logging import log

# Mantém o login resiliente sem prender a execução em tentativas excessivas.
MAX_TENTATIVAS_LOGIN = 2


class ExecutorEmLote:
    """Orquestra o processamento das contas com suporte a múltiplas ações."""

    @staticmethod
    def _normalizar_acoes(acoes: Iterable[str]) -> List[str]:
        """Normaliza nomes de ações removendo espaços extras e aplicando minúsculas."""

        return [
            item.strip().lower()
            for item in acoes
            if isinstance(item, str) and item.strip()
        ]

    def __init__(
        self,
        arquivo_usuarios: str | None = None,
        acoes: Iterable[str] | str | None = None,
        max_workers: int | None = None,
        *,
        config: ExecutorConfig | None = None,
    ) -> None:
        base_config = (
            config.clone()
            if config
            else ExecutorConfig.from_env(fallback_file=arquivo_usuarios)
        )

        if arquivo_usuarios:
            base_config.users_file = arquivo_usuarios

        if acoes is not None:
            itens = acoes.split(",") if isinstance(acoes, str) else list(acoes)
            normalizadas = self._normalizar_acoes(itens)
            base_config.actions = normalizadas or list(DEFAULT_ACTIONS)

        if max_workers is not None:
            if max_workers >= 1:
                base_config.max_workers = max_workers
            else:
                log.aviso("Valor invalido para max_workers", valor=max_workers)

        self._config = base_config
        self.arquivo_usuarios = self._config.users_file
        self.acoes = list(self._config.actions)
        self.contas: List[Conta] = []
        self._palavras_erro_api = list(self._config.api_error_words)
        self._max_workers = self._config.max_workers
        self._acoes_map = {
            "login": self.acao_login,
            "rewards": self.acao_rewards,
            "solicitacoes": self.acao_solicitacoes,
        }
        log.atualizar_contexto_padrao(arquivo=self.arquivo_usuarios)
        log.debug(
            "Executor inicializado",
            acoes=self.acoes,
            palavras_erro=len(self._palavras_erro_api),
            max_workers=self._max_workers,
        )

    def executar(self) -> None:
        if not self.carregar_contas():
            return

        if self._max_workers <= 1 or len(self.contas) <= 1:
            for conta in self.contas:
                self.processar_conta(conta)
            return

        workers = max(1, min(self._max_workers, len(self.contas)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futuros = {
                executor.submit(self.processar_conta, conta): conta for conta in self.contas
            }
            for futuro in as_completed(futuros):
                conta = futuros[futuro]
                try:
                    futuro.result()
                except Exception as exc:  # pragma: no cover - depende do ambiente de execucao
                    log.erro(
                        "Processamento paralelo falhou",
                        email=conta.email,
                        perfil=conta.id_perfil,
                        detalhe=str(exc),
                    )
                    raise

    def carregar_contas(self) -> bool:
        """Carrega as contas do arquivo configurado e registra métricas."""

        try:
            self.contas = carregar_contas(self.arquivo_usuarios)
        except FileNotFoundError as exc:
            log.erro("Arquivo de contas ausente", detalhe=str(exc))
            return False

        if not self.contas:
            log.aviso("Nenhuma conta valida encontrada")
            return False

        log.info("Contas carregadas", total=len(self.contas))
        return True

    def processar_conta(self, conta: Conta) -> None:
        """Executa as ações configuradas para uma conta específica."""

        perfil = conta.id_perfil
        argumentos = GerenciadorPerfil.argumentos_agente_usuario(perfil)
        registro = log.com_contexto(email=conta.email, perfil=perfil)

        registro.info("Processando conta")

        solicitacoes: GerenciadorSolicitacoesRewards | None = None
        api: APIRecompensas | None = None

        for acao in self.acoes:
            handler = self._acoes_map.get(acao)
            if handler is None:
                registro.aviso("Acao desconhecida ignorada", acao=acao)
                continue

            try:
                if acao == "login":
                    resultado = handler(
                        conta=conta,
                        perfil=perfil,
                        argumentos=argumentos,
                        registro=registro,
                    )
                elif acao == "rewards":
                    resultado = handler(
                        perfil=perfil,
                        argumentos=argumentos,
                        registro=registro,
                    )
                else:  # solicitacoes
                    resultado = handler(
                        conta=conta,
                        perfil=perfil,
                        registro=registro,
                        solicitacoes=solicitacoes,
                        api=api,
                    )
            except Exception as exc:
                registro.erro("Acao falhou", acao=acao, detalhe=str(exc))
                raise

            if acao == "login" and isinstance(resultado, tuple):
                solicitacoes, api = resultado

    def salvar_resposta_debug(
        self,
        conta: Conta,
        perfil: str,
        registro: Any,
        nome: str,
        dados: Any,
    ) -> None:
        """Persiste respostas de API para análise posterior."""

        destino = Path.cwd() / "debug_respostas"
        identificador = perfil or conta.id_perfil
        arquivo = destino / f"{identificador}_{nome}.json"

        try:
            destino.mkdir(parents=True, exist_ok=True)
            if isinstance(dados, bytes):
                conteudo = dados.decode("utf-8", errors="replace")
            elif isinstance(dados, str):
                conteudo = dados
            else:
                conteudo = json.dumps(dados, ensure_ascii=False, indent=2)
        except Exception as exc:
            registro.aviso(
                "Nao foi possivel serializar resposta para debug",
                detalhe=str(exc),
            )
            conteudo = str(dados)

        try:
            arquivo.write_text(conteudo, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - depende do FS
            registro.aviso(
                "Falha ao gravar arquivo de debug",
                caminho=str(arquivo),
                detalhe=str(exc),
            )
        else:
            registro.debug(
                "Resposta salva para analise",
                arquivo=str(arquivo),
            )

    def acao_rewards(
        self,
        *,
        perfil: str,
        argumentos: List[str],
        registro: Any,
        solicitacoes: GerenciadorSolicitacoesRewards | None = None,
        api: APIRecompensas | None = None,
    ) -> None:
        """Abre a página principal do Rewards para a conta atual."""

        registro.info("Abrindo pagina de rewards")
        NavegadorRecompensas.abrir_pagina(
            profile=perfil,
            add_arguments=argumentos,
        )
        registro.sucesso("Rewards acessado com sucesso")

    def acao_login(
        self,
        *,
        conta: Conta,
        perfil: str,
        argumentos: List[str],
        registro: Any,
        solicitacoes: GerenciadorSolicitacoesRewards | None = None,
        api: APIRecompensas | None = None,
    ) -> tuple[GerenciadorSolicitacoesRewards, APIRecompensas]:
        """Realiza o fluxo de login com tentativas controladas."""

        registro.info("Iniciando login")
        for tentativa in range(1, MAX_TENTATIVAS_LOGIN + 1):
            try:
                if tentativa > 1:
                    atraso = 2 ** (tentativa - 1)
                    registro.info(
                        "Repetindo tentativa de login",
                        tentativa=tentativa,
                        aguardando=f"{atraso}s",
                    )
                    time.sleep(atraso)

                gerenciador = AutenticadorRewards.executar(
                    profile=perfil,
                    add_arguments=argumentos,
                    data={"email": conta.email, "senha": conta.senha},
                )

                api = APIRecompensas(
                    gerenciador,
                    palavras_erro=self._palavras_erro_api,
                )

                sessao = gerenciador.dados_sessao
                total_cookies = len(sessao.cookies) if sessao else 0
                registro.debug(
                    "Sessao de solicitacoes capturada",
                    total_cookies=total_cookies,
                )
                mensagem = (
                    "Login concluido apos nova tentativa"
                    if tentativa > 1
                    else "Login concluido"
                )
                registro.sucesso(mensagem)
                return gerenciador, api

            except Exception as exc:
                if tentativa == MAX_TENTATIVAS_LOGIN:
                    raise RuntimeError(
                        f"Login impossivel para {conta.email}: {exc}"
                    ) from exc
                registro.aviso(
                    "Tentativa de login falhou",
                    tentativa=tentativa,
                    detalhe=str(exc),
                )

    def acao_solicitacoes(
        self,
        *,
        conta: Conta,
        perfil: str,
        registro: Any,
        solicitacoes: GerenciadorSolicitacoesRewards | None,
        api: APIRecompensas | None,
    ) -> None:
        """Consulta pontos e recompensas usando a API autenticada."""

        registro.info("Consultando API do Rewards com sessao autenticada")

        if solicitacoes is None or api is None:
            registro.aviso(
                "Sessao de solicitacoes indisponivel",
                detalhe="Execute a acao 'login' antes de 'solicitacoes'",
            )
            return

        try:
            pontos = api.obter_pontos(
                palavras_erro=self._palavras_erro_api,
            )
        except Exception as exc:
            registro.erro("Falha ao obter pontos do Rewards", detalhe=str(exc))
        else:
            self.salvar_resposta_debug(conta, perfil, registro, "pontos", pontos)
            valor_pontos = (
                APIRecompensas.extrair_pontos_disponiveis(pontos)
                if isinstance(pontos, Mapping)
                else None
            )
            registro.sucesso(
                "Pontos consultados",
                chave="availablePoints",
                valor=valor_pontos,
            )

        try:
            recompensas = api.obter_recompensas(
                palavras_erro=self._palavras_erro_api,
            )
        except Exception as exc:
            registro.erro("Falha ao obter recompensas", detalhe=str(exc))
        else:
            tipos = APIRecompensas.contar_recompensas_por_tipo(recompensas)
            quantidade = APIRecompensas.contar_recompensas(recompensas)
            registro.sucesso(
                "Recompensas consultadas",
                chave="total",
                quantidade=quantidade,
                tipos=tipos,
            )

            resumo_tarefas = api.executar_tarefas(recompensas, registro=registro)
            if resumo_tarefas.get("total"):
                if resumo_tarefas.get("executadas"):
                    registro.sucesso(
                        "Tarefas rewards executadas",
                        concluidas=resumo_tarefas["executadas"],
                        falhas=resumo_tarefas["falhas"],
                        ignoradas=resumo_tarefas["ignoradas"],
                    )
                elif resumo_tarefas.get("falhas"):
                    registro.aviso(
                        "Tarefas rewards apresentaram falhas",
                        falhas=resumo_tarefas["falhas"],
                        ignoradas=resumo_tarefas["ignoradas"],
                    )
                elif resumo_tarefas.get("ja_concluidas"):
                    registro.info(
                        "Tarefas rewards ja estavam concluidas",
                        concluidas=resumo_tarefas["ja_concluidas"],
                        ignoradas=resumo_tarefas["ignoradas"],
                    )
                elif resumo_tarefas.get("ignoradas"):
                    registro.aviso(
                        "Tarefas rewards ignoradas",
                        ignoradas=resumo_tarefas["ignoradas"],
                    )


def executar_cli() -> None:
    """Ponto de entrada padrão para execução via CLI."""

    ExecutorEmLote().executar()


__all__ = [
    "ExecutorEmLote",
    "executar_cli",
]
