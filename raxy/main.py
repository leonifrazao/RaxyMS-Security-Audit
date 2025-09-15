"""Executor em batch das contas definidas em ``users.txt``.

Formato do arquivo ``users.txt`` (uma conta por linha)::

    email:senha

Linhas em branco ou iniciadas por ``#`` sao ignoradas.
"""

from __future__ import annotations

import os
from typing import Iterable, List

from src import AutenticadorRewards, NavegadorRecompensas, GerenciadorPerfil
from src.contas import Conta, carregar_contas
from src.logging import log


class ExecutorEmLote:
    """Orquestra o processamento das contas com suporte a diferentes acoes."""

    def __init__(
        self,
        arquivo_usuarios: str | None = None,
        acoes: Iterable[str] | str | None = None,
    ) -> None:
        self.arquivo_usuarios = arquivo_usuarios or os.getenv("USERS_FILE", "users.txt")
        self.acoes = self._normalizar_acoes(acoes or os.getenv("ACTIONS", "login,rewards"))
        self.contas: List[Conta] = []
        log.atualizar_contexto_padrao(arquivo=self.arquivo_usuarios)
        log.debug("Lista de acoes normalizada", acoes=self.acoes)

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
        for conta in self.contas:
            self._processar_conta(conta)

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
        argumentos_navegador = GerenciadorPerfil.argumentos_agente_usuario(perfil)

        registro_conta = log.com_contexto(email=conta.email, perfil=perfil)
        registro_conta.info("Processando conta")

        if "login" in self.acoes:
            self._executar_login(conta, argumentos_navegador, registro_conta)

        if "rewards" in self.acoes:
            self._abrir_recompensas(perfil, argumentos_navegador, registro_conta)

    def _executar_login(self, conta: Conta, argumentos_navegador: List[str], registro_conta) -> None:
        try:
            with registro_conta.etapa(
                "Login",
                mensagem_inicial="Iniciando login",
                mensagem_sucesso="Login concluido",
            ):
                AutenticadorRewards.executar(
                    profile=conta.id_perfil,
                    add_arguments=argumentos_navegador,
                    data={"email": conta.email, "senha": conta.senha},
                )
        except Exception as exc:
            registro_conta.erro("Erro durante login", detalhe=str(exc))

    def _abrir_recompensas(self, perfil: str, argumentos_navegador: List[str], registro_conta) -> None:
        try:
            with registro_conta.etapa(
                "Rewards",
                mensagem_inicial="Abrindo pagina de rewards",
                mensagem_sucesso="Rewards acessado",
            ):
                NavegadorRecompensas.abrir_pagina(
                    profile=perfil,
                    add_arguments=argumentos_navegador,
                )
        except Exception as exc:
            registro_conta.erro("Erro durante rewards", detalhe=str(exc))


def main() -> None:
    """Ponto de entrada da aplicacao em modo script."""

    ExecutorEmLote().executar()


if __name__ == "__main__":
    main()
