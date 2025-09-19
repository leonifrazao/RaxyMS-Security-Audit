"""Serviços de orquestração para processamento em lote das contas."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, List, Mapping, Optional

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


@dataclass(slots=True)
class ContextoConta:
    """Encapsula os dados necessários para processar uma conta."""

    conta: Conta
    perfil: str
    argumentos_navegador: List[str]
    registro: Any
    solicitacoes: GerenciadorSolicitacoesRewards | None = None
    api: APIRecompensas | None = None

    def registrar_solicitacoes(
        self,
        gerenciador: GerenciadorSolicitacoesRewards,
        palavras_erro: List[str],
        *,
        interativo: Optional[bool] = None,
    ) -> None:
        """Sincroniza utilidades de requisição após um login bem-sucedido."""

        self.solicitacoes = gerenciador
        self.api = APIRecompensas(
            gerenciador,
            palavras_erro=palavras_erro,
            interativo=interativo,
        )


class ExecutorEmLote:
    """Orquestra o processamento das contas com suporte a múltiplas ações."""

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
            normalizadas = self._normalizar_acoes(acoes)
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
        self._handlers: dict[str, Callable[[ContextoConta], None]] = {
            "login": self._acao_login,
            "rewards": self._acao_rewards,
            "solicitacoes": self._acao_solicitacoes,
        }

        log.atualizar_contexto_padrao(arquivo=self.arquivo_usuarios)
        log.debug(
            "Executor inicializado",
            acoes=self.acoes,
            palavras_erro=len(self._palavras_erro_api),
            max_workers=self._max_workers,
        )

    @staticmethod
    def _normalizar_acoes(acoes: Iterable[str] | str) -> List[str]:
        if isinstance(acoes, str):
            itens = acoes.split(",")
        else:
            itens = list(acoes)
        return [item.strip().lower() for item in itens if item and item.strip()]

    def executar(self) -> None:
        if not self._carregar_contas():
            return

        if self._max_workers <= 1 or len(self.contas) <= 1:
            for conta in self.contas:
                self._processar_conta(conta)
            return

        workers = max(1, min(self._max_workers, len(self.contas)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futuros = {executor.submit(self._processar_conta, conta): conta for conta in self.contas}
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

    def _carregar_contas(self) -> bool:
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

    def _processar_conta(self, conta: Conta) -> None:
        perfil = conta.id_perfil
        argumentos = GerenciadorPerfil.argumentos_agente_usuario(perfil)
        contexto = ContextoConta(
            conta=conta,
            perfil=perfil,
            argumentos_navegador=argumentos,
            registro=log.com_contexto(email=conta.email, perfil=perfil),
        )

        contexto.registro.info("Processando conta")

        for acao in self.acoes:
            handler = self._handlers.get(acao)
            if handler is None:
                contexto.registro.aviso("Acao desconhecida ignorada", acao=acao)
                continue

            try:
                handler(contexto)
            except Exception as exc:
                contexto.registro.erro(
                    "Acao falhou",
                    acao=acao,
                    detalhe=str(exc),
                )
                raise

    def _acao_rewards(self, contexto: ContextoConta) -> None:
        contexto.registro.info("Abrindo pagina de rewards")
        NavegadorRecompensas.abrir_pagina(
            profile=contexto.perfil,
            add_arguments=contexto.argumentos_navegador,
        )
        contexto.registro.sucesso("Rewards acessado com sucesso")

    def _acao_login(self, contexto: ContextoConta) -> None:
        interatividade_api = self._modo_interativo_api()
        contexto.registro.info("Iniciando login")
        for tentativa in range(1, MAX_TENTATIVAS_LOGIN + 1):
            try:
                if tentativa > 1:
                    atraso = 2 ** (tentativa - 1)
                    contexto.registro.info(
                        "Repetindo tentativa de login",
                        tentativa=tentativa,
                        aguardando=f"{atraso}s",
                    )
                    time.sleep(atraso)

                gerenciador = AutenticadorRewards.executar(
                    profile=contexto.perfil,
                    add_arguments=contexto.argumentos_navegador,
                    data={"email": contexto.conta.email, "senha": contexto.conta.senha},
                )

                contexto.registrar_solicitacoes(
                    gerenciador,
                    self._palavras_erro_api,
                    interativo=interatividade_api,
                )

                sessao = gerenciador.dados_sessao
                total_cookies = len(sessao.cookies) if sessao else 0
                contexto.registro.debug(
                    "Sessao de solicitacoes capturada",
                    total_cookies=total_cookies,
                )
                mensagem = (
                    "Login concluido apos nova tentativa"
                    if tentativa > 1
                    else "Login concluido"
                )
                contexto.registro.sucesso(mensagem)
                return

            except Exception as exc:
                if tentativa == MAX_TENTATIVAS_LOGIN:
                    raise RuntimeError(
                        f"Login impossivel para {contexto.conta.email}: {exc}"
                    ) from exc
                contexto.registro.aviso(
                    "Tentativa de login falhou",
                    tentativa=tentativa,
                    detalhe=str(exc),
                )

    def _acao_solicitacoes(self, contexto: ContextoConta) -> None:
        contexto.registro.info("Consultando API do Rewards com sessao autenticada")

        if contexto.solicitacoes is None or contexto.api is None:
            contexto.registro.aviso(
                "Sessao de solicitacoes indisponivel",
                detalhe="Execute a acao 'login' antes de 'solicitacoes'",
            )
            return

        api = contexto.api
        interatividade_api = self._modo_interativo_api()

        try:
            pontos = api.obter_pontos(
                palavras_erro=self._palavras_erro_api,
                interativo=interatividade_api,
            )
        except Exception as exc:
            contexto.registro.erro("Falha ao obter pontos do Rewards", detalhe=str(exc))
        else:
            self._salvar_resposta_debug(contexto, "pontos", pontos)
            valor_pontos = (
                APIRecompensas.extrair_pontos_disponiveis(pontos)
                if isinstance(pontos, Mapping)
                else None
            )
            contexto.registro.sucesso(
                "Pontos consultados",
                chave="availablePoints",
                valor=valor_pontos,
            )

        try:
            recompensas = api.obter_recompensas(
                palavras_erro=self._palavras_erro_api,
                interativo=interatividade_api,
            )
        except Exception as exc:
            contexto.registro.erro("Falha ao obter recompensas", detalhe=str(exc))
        else:
            quantidade = APIRecompensas.contar_recompensas(recompensas)
            contexto.registro.sucesso(
                "Recompensas consultadas",
                chave="total",
                quantidade=quantidade,
            )

    def _salvar_resposta_debug(self, contexto: ContextoConta, nome: str, dados: Any) -> None:
        destino = Path.cwd() / "debug_respostas"
        identificador = contexto.perfil or contexto.conta.id_perfil
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
            contexto.registro.aviso(
                "Nao foi possivel serializar resposta para debug",
                detalhe=str(exc),
            )
            conteudo = str(dados)

        try:
            arquivo.write_text(conteudo, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - depende do FS
            contexto.registro.aviso(
                "Falha ao gravar arquivo de debug",
                caminho=str(arquivo),
                detalhe=str(exc),
            )
        else:
            contexto.registro.debug(
                "Resposta salva para analise",
                arquivo=str(arquivo),
            )

    def _modo_interativo_api(self) -> Optional[bool]:
        return self._config.api_interactivity()


def executar_cli() -> None:
    """Ponto de entrada padrão para execução via CLI."""

    ExecutorEmLote().executar()


__all__ = [
    "ExecutorEmLote",
    "ContextoConta",
    "executar_cli",
]
