"""Implementações de repositório baseadas em arquivos texto."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence, Optional

from raxy.domain import Conta
from raxy.interfaces.storage import IFileSystem
from raxy.core.exceptions import (
    FileRepositoryException,
    DataValidationException,
    DataNotFoundException,
    wrap_exception,
)
from raxy.core.logging import get_logger


def carregar_contas(
    caminho_arquivo: str | Path,
    filesystem: Optional[IFileSystem] = None
) -> list[Conta]:
    """
    Carrega contas de um arquivo com tratamento robusto de erros.
    
    Args:
        caminho_arquivo: Caminho do arquivo
        filesystem: Sistema de arquivos (se None, usa LocalFileSystem)
    """
    # Usa LocalFileSystem se não fornecido
    if filesystem is None:
        from raxy.infrastructure.storage import LocalFileSystem
        filesystem = LocalFileSystem()
    
    caminho = str(caminho_arquivo)
    
    if not filesystem.exists(caminho):
        raise DataNotFoundException(
            f"Arquivo não encontrado: {caminho}",
            details={"caminho": caminho}
        )

    logger = get_logger()
    logger.debug(f"Carregando contas de: {caminho}")

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

    logger.info(f"Carregadas {len(contas)} contas de {caminho}")
    return contas

from raxy.interfaces.repositories import IContaRepository, IHistoricoPontuacaoRepository

__all__ = [
    "ArquivoContaRepository",
    "HistoricoPontuacaoMemoriaRepository",
    "carregar_contas",
]


class ArquivoContaRepository(IContaRepository):
    """
    Realiza operações de persistência em um arquivo ``email:senha``.
    
    Desacoplado do filesystem através da interface IFileSystem,
    permitindo trocar entre local, cloud (S3), ou mock para testes.
    
    Design Pattern: Dependency Injection
    Princípio: Dependency Inversion Principle (DIP)
    """

    def __init__(
        self,
        caminho_arquivo: str | Path,
        filesystem: Optional[IFileSystem] = None
    ) -> None:
        """
        Inicializa o repositório.
        
        Args:
            caminho_arquivo: Caminho do arquivo de contas
            filesystem: Sistema de arquivos (se None, usa LocalFileSystem)
        """
        try:
            self._caminho = str(caminho_arquivo)
            
            # Dependency Injection: recebe filesystem ou cria padrão
            if filesystem is None:
                from raxy.infrastructure.storage import LocalFileSystem
                filesystem = LocalFileSystem()
            
            self._filesystem = filesystem
        except Exception as e:
            raise wrap_exception(
                e, FileRepositoryException,
                "Erro ao inicializar repositório",
                caminho=str(caminho_arquivo)
            )

    def listar(self) -> list[Conta]:
        """Lista todas as contas com tratamento de erros."""
        try:
            return carregar_contas(self._caminho, self._filesystem)
        except DataNotFoundException:
            # Se arquivo não existe, retorna lista vazia
            return []
        except (DataValidationException, FileRepositoryException):
            raise
        except Exception as e:
            raise wrap_exception(
                e, FileRepositoryException,
                "Erro ao listar contas",
                caminho=self._caminho
            )

    def salvar(self, conta: Conta) -> Conta:
        """Salva uma conta com tratamento de erros."""
        try:
            contas = {item.email: item for item in self.listar()}
            contas[conta.email] = conta
            self._persistir(contas.values())
            return conta
        except (FileRepositoryException, DataValidationException):
            raise
        except Exception as e:
            raise wrap_exception(
                e, FileRepositoryException,
                "Erro ao salvar conta",
                email=conta.email
            )

    def salvar_varias(self, contas: Iterable[Conta]) -> Sequence[Conta]:
        """Salva várias contas com tratamento de erros."""
        try:
            existentes = {item.email: item for item in self.listar()}
            for conta in contas:
                existentes[conta.email] = conta
            self._persistir(existentes.values())
            return list(existentes.values())
        except (FileRepositoryException, DataValidationException):
            raise
        except Exception as e:
            raise wrap_exception(
                e, FileRepositoryException,
                "Erro ao salvar várias contas",
                total_contas=len(list(contas))
            )

    def remover(self, conta: Conta) -> None:
        """Remove uma conta com tratamento de erros."""
        try:
            contas = [item for item in self.listar() if item.email != conta.email]
            self._persistir(contas)
        except (FileRepositoryException, DataValidationException):
            raise
        except Exception as e:
            raise wrap_exception(
                e, FileRepositoryException,
                "Erro ao remover conta",
                email=conta.email
            )

    def _persistir(self, contas: Iterable[Conta]) -> None:
        """Persiste contas no arquivo com tratamento de erros."""
        try:
            linhas = [f"{conta.email}:{conta.senha}\n" for conta in contas]
            conteudo = "".join(linhas)
        except Exception as e:
            raise wrap_exception(
                e, FileRepositoryException,
                "Erro ao formatar contas para persistência"
            )
        
        try:
            # write_text já cria diretórios automaticamente (create_dirs=True)
            self._filesystem.write_text(
                self._caminho,
                conteudo,
                encoding="utf-8",
                create_dirs=True
            )
        except OSError as e:
            raise wrap_exception(
                e, FileRepositoryException,
                "Erro ao escrever arquivo de contas",
                caminho=self._caminho
            )
        except Exception as e:
            raise wrap_exception(
                e, FileRepositoryException,
                "Erro inesperado ao persistir contas",
                caminho=self._caminho
            )


class HistoricoPontuacaoMemoriaRepository(IHistoricoPontuacaoRepository):
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
