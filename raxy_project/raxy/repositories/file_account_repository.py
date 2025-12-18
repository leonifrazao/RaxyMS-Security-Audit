"""Implementações de repositório baseadas em arquivos texto."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence, Optional, Any

from raxy.domain import Conta
from raxy.core.exceptions import (
    FileRepositoryException,
    DataValidationException,
    DataNotFoundException,
    wrap_exception,
)


def carregar_contas(
    caminho_arquivo: str | Path,
    filesystem: Optional[Any] = None
) -> list[Conta]:
    """
    Carrega contas de um arquivo com tratamento robusto de erros.
    
    Args:
        caminho_arquivo: Caminho do arquivo
        filesystem: Sistema de arquivos (se None, usa LocalFileSystem)
    """
    # Usa LocalFileSystem se não fornecido
    if filesystem is None:
        from raxy.storage import LocalFileSystem
        filesystem = LocalFileSystem()
    
    caminho = str(caminho_arquivo)
    
    if not filesystem.exists(caminho):
        raise DataNotFoundException(
            f"Arquivo não encontrado: {caminho}",
            details={"caminho": caminho}
        )

    try:
        conteudo = filesystem.read_text(caminho, encoding="utf-8")
    except UnicodeDecodeError as e:
        raise wrap_exception(
            e, FileRepositoryException,
            "Erro de codificação ao ler arquivo",
            caminho=caminho
        )
    except Exception as e:
        raise wrap_exception(
            e, FileRepositoryException,
            "Erro ao ler arquivo de contas",
            caminho=caminho
        )

    contas: list[Conta] = []
    for numero_linha, linha in enumerate(conteudo.splitlines(), start=1):
        try:
            linha = linha.strip()
            if not linha or linha.startswith("#") or ":" not in linha:
                continue

            email, senha = (parte.strip() for parte in linha.split(":", 1))
            if not email or not senha:
                continue

            # Validação básica de email
            if "@" not in email:
                raise DataValidationException(
                    f"Email inválido na linha {numero_linha}",
                    details={"email": email, "linha": numero_linha}
                )

            base = email.lower().replace("@", "_at_")
            id_perfil = re.sub(r"[^a-z0-9._-]+", "_", base).strip("_") or "perfil"
            contas.append(Conta(email=email, senha=senha, id_perfil=id_perfil))
        except DataValidationException:
            # Re-lança exceções de validação
            raise
        except Exception as e:
            # Ignora linhas problemáticas mas continua processando
            pass

    return contas


class ArquivoContaRepository:
    """Repositório de contas baseado em arquivo."""
    
    def __init__(self, caminho_arquivo: str | Path, filesystem: Optional[Any] = None):
        self.caminho_arquivo = caminho_arquivo
        self.filesystem = filesystem
        
    def listar(self) -> list[Conta]:
        """Lista todas as contas do arquivo."""
        return carregar_contas(self.caminho_arquivo, self.filesystem)


class HistoricoPontuacaoMemoriaRepository:
    """Implementa o registro de pontos em memória (útil para testes) com tratamento de erros."""

    def __init__(self) -> None:
        try:
            self._ultimos: dict[str, int] = {}
        except Exception as e:
            raise wrap_exception(
                e, FileRepositoryException,
                "Erro ao inicializar repositório de histórico"
            )

    def registrar_pontos(self, conta: Conta, pontos: int) -> None:
        """Registra pontos com validação."""
        try:
            if not isinstance(pontos, int) or pontos < 0:
                raise DataValidationException(
                    "Pontos devem ser um inteiro não-negativo",
                    details={"pontos": pontos, "tipo": type(pontos).__name__}
                )
            self._ultimos[conta.email] = pontos
        except DataValidationException:
            raise
        except Exception as e:
            raise wrap_exception(
                e, FileRepositoryException,
                "Erro ao registrar pontos",
                email=conta.email, pontos=pontos
            )

    def obter_ultimo_total(self, conta: Conta) -> int | None:
        """Obtém o último total com tratamento de erros."""
        try:
            return self._ultimos.get(conta.email)
        except Exception as e:
            # Retorna None em caso de erro
            return None
