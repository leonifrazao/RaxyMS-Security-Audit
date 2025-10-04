"""Camada de logging baseada em Loguru com API em português.

Esta versão oferece recurso de contexto, integração com arquivos JSON
rotacionáveis e uma interface simplificada para uso em automações.
"""

from __future__ import annotations

import dataclasses
import os
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from loguru import logger as _loguru_logger

from raxy.interfaces.services import ILoggingService


# ---------------------------------------------------------------------------
# Configuração de níveis e aliases
# ---------------------------------------------------------------------------

_LEVEL_MAP: dict[str, int] = {
    "debug": 10,
    "info": 20,
    "sucesso": 25,
    "success": 25,
    "aviso": 30,
    "warning": 30,
    "erro": 40,
    "error": 40,
    "critico": 50,
    "critical": 50,
}

_LOGURU_NAME_MAP: dict[str, str] = {
    "debug": "DEBUG",
    "info": "INFO",
    "sucesso": "SUCESSO",
    "success": "SUCCESS",
    "aviso": "WARNING",
    "warning": "WARNING",
    "erro": "ERROR",
    "error": "ERROR",
    "critico": "CRITICAL",
    "critical": "CRITICAL",
}

try:
    _loguru_logger.level("SUCESSO")
except ValueError:
    _loguru_logger.level("SUCESSO", no=25, color="<green>")


# ---------------------------------------------------------------------------
# Configuração centralizada
# ---------------------------------------------------------------------------


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(slots=True)
class LoggerConfig:
    """Configuração centralizada do logger.

    O comportamento padrão privilegia a saída em console com cores, mas o
    serviço suporta escrita em arquivo rotacionado e ajustes via variáveis de
    ambiente. Todos os campos continuam em português para facilitar a leitura
    pelos times que mantêm o projeto.
    """

    nome: str = "farm"
    nivel_minimo: str | int = "INFO"
    arquivo_log: str | Path | None = None
    sobrescrever_arquivo: bool = False
    mostrar_tempo: bool = True
    registrar_traceback_rico: bool = True
    usar_cores: bool = True
    rotacao_arquivo: str | int | None = None
    retencao_arquivo: str | int | None = None
    compressao_arquivo: str | None = None

    @classmethod
    def from_env(cls) -> "LoggerConfig":
        """Cria uma configuração com base nas variáveis de ambiente."""

        cfg = cls()

        nivel = os.getenv("LOG_LEVEL")
        if nivel:
            cfg.nivel_minimo = nivel

        arquivo = os.getenv("LOG_FILE")
        if arquivo:
            cfg.arquivo_log = arquivo

        cfg.sobrescrever_arquivo = _parse_bool(os.getenv("LOG_OVERWRITE"), cfg.sobrescrever_arquivo)
        cfg.mostrar_tempo = _parse_bool(os.getenv("LOG_SHOW_TIME"), cfg.mostrar_tempo)
        cfg.usar_cores = _parse_bool(os.getenv("LOG_COLOR"), cfg.usar_cores)
        cfg.registrar_traceback_rico = _parse_bool(
            os.getenv("LOG_RICH_TRACEBACK"), cfg.registrar_traceback_rico
        )

        rotacao = os.getenv("LOG_ROTATION")
        if rotacao:
            cfg.rotacao_arquivo = rotacao

        retencao = os.getenv("LOG_RETENTION")
        if retencao:
            cfg.retencao_arquivo = retencao

        compressao = os.getenv("LOG_COMPRESSION")
        if compressao:
            cfg.compressao_arquivo = compressao

        return cfg


# ---------------------------------------------------------------------------
# Implementação principal
# ---------------------------------------------------------------------------


class FarmLogger(ILoggingService):
    """Implementação principal do logger com API em português."""

    def __init__(self) -> None:
        self._config = LoggerConfig()
        self._nivel_minimo = self._resolver_nivel_valor(self._config.nivel_minimo)
        self._contexto_padrao: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._sink_ids: list[int] = []
        self._file_sink_id: Optional[int] = None
        self._logger = _loguru_logger.bind(contexto={}, dados={}, suffix="")
        self.configure(self._config)

    # ------------------------------------------------------------------
    # Configuração e contexto
    # ------------------------------------------------------------------

    @property
    def config(self) -> LoggerConfig:
        """Retorna a configuração ativa para inspeção."""

        return self._config

    def configure(self, config: LoggerConfig) -> None:
        """Aplica uma nova configuração ao logger."""

        with self._lock:
            self._config = config
            self._nivel_minimo = self._resolver_nivel_valor(config.nivel_minimo)

            for sink_id in self._sink_ids:
                try:
                    _loguru_logger.remove(sink_id)
                except ValueError:
                    pass
            self._sink_ids.clear()
            self._file_sink_id = None

            self._logger = _loguru_logger.bind(contexto={}, dados={}, suffix="")
            nivel_loguru = self._resolver_loguru_nome(config.nivel_minimo)

            formato_console = self._construir_formato_console(config)
            console_sink_id = _loguru_logger.add(
                sys.stdout,
                format=formato_console,
                colorize=config.usar_cores,
                level=nivel_loguru,
                enqueue=False,
                backtrace=config.registrar_traceback_rico,
                diagnose=False,
            )
            self._sink_ids.append(console_sink_id)

            if config.arquivo_log:
                path = Path(config.arquivo_log)
                path.parent.mkdir(parents=True, exist_ok=True)

                kwargs: dict[str, Any] = {
                    "level": nivel_loguru,
                    "enqueue": True,
                    "mode": "w" if config.sobrescrever_arquivo else "a",
                    "serialize": True,
                    "backtrace": config.registrar_traceback_rico,
                    "diagnose": False,
                }
                if config.rotacao_arquivo is not None:
                    kwargs["rotation"] = config.rotacao_arquivo
                if config.retencao_arquivo is not None:
                    kwargs["retention"] = config.retencao_arquivo
                if config.compressao_arquivo is not None:
                    kwargs["compression"] = config.compressao_arquivo

                file_sink_id = _loguru_logger.add(str(path), **kwargs)
                self._sink_ids.append(file_sink_id)
                self._file_sink_id = file_sink_id

    def atualizar_contexto_padrao(self, **dados: Any) -> None:
        """Adiciona ou atualiza campos que aparecem em todos os logs."""

        with self._lock:
            filtrados = {k: v for k, v in dados.items() if v is not None}
            self._contexto_padrao.update(filtrados)

    def limpar_contexto_padrao(self, *chaves: str) -> None:
        """Remove campos do contexto padrão."""

        with self._lock:
            if not chaves:
                self._contexto_padrao.clear()
                return
            for chave in chaves:
                self._contexto_padrao.pop(chave, None)

    def com_contexto(self, **dados: Any) -> "ScopedLogger":
        """Retorna um logger derivado com contexto adicional."""

        contexto = {k: v for k, v in dados.items() if v is not None}
        return ScopedLogger(self, contexto)

    # ------------------------------------------------------------------
    # API pública de logging
    # ------------------------------------------------------------------

    def debug(self, mensagem: str, **dados: Any) -> None:
        self.registrar_evento("debug", mensagem, dados, None)

    def info(self, mensagem: str, **dados: Any) -> None:
        self.registrar_evento("info", mensagem, dados, None)

    def sucesso(self, mensagem: str, **dados: Any) -> None:
        self.registrar_evento("sucesso", mensagem, dados, None)

    def aviso(self, mensagem: str, **dados: Any) -> None:
        self.registrar_evento("aviso", mensagem, dados, None)

    def erro(self, mensagem: str, **dados: Any) -> None:
        self.registrar_evento("erro", mensagem, dados, None)

    def critico(self, mensagem: str, **dados: Any) -> None:
        self.registrar_evento("critico", mensagem, dados, None)

    @contextmanager
    def etapa(
        self,
        titulo: str,
        mensagem_inicial: Optional[str] = None,
        mensagem_sucesso: Optional[str] = None,
        mensagem_falha: Optional[str] = None,
        **dados: Any,
    ):
        dados_limpos = {k: v for k, v in dados.items() if v is not None}
        inicio = mensagem_inicial or f"Iniciando etapa: {titulo}"
        sucesso_msg = mensagem_sucesso or f"Etapa concluida: {titulo}"
        falha_msg = mensagem_falha or f"Falha na etapa: {titulo}"

        self.registrar_evento("info", inicio, dados_limpos, None)
        try:
            yield
        except Exception:
            self.registrar_evento("erro", falha_msg, dados_limpos, None)
            raise
        else:
            self.registrar_evento("sucesso", sucesso_msg, dados_limpos, None)

    # ------------------------------------------------------------------
    # Implementação interna
    # ------------------------------------------------------------------

    def deve_emitir(self, nivel: str | int) -> bool:
        if isinstance(nivel, int):
            valor = nivel
        else:
            valor = self._resolver_nivel_valor(nivel)
        return valor >= self._nivel_minimo

    def registrar_evento(
        self,
        nivel: str | int,
        mensagem: str,
        dados: Mapping[str, Any] | None,
        contexto_extra: Optional[Mapping[str, Any]],
    ) -> None:
        if not self.deve_emitir(nivel):
            return

        dados_limpos = {k: v for k, v in (dados or {}).items() if v is not None}
        nivel_loguru = self._resolver_loguru_nome(nivel)

        with self._lock:
            contexto: dict[str, Any] = {
                k: v for k, v in self._contexto_padrao.items() if v is not None
            }
            if contexto_extra:
                for chave, valor in contexto_extra.items():
                    if valor is not None:
                        contexto[chave] = valor

            contexto_repr = {k: self.formatar_valor(v) for k, v in contexto.items()}
            dados_repr = {k: self.formatar_valor(v) for k, v in dados_limpos.items()}
            contexto_extra = self._normalizar_extra(contexto)
            dados_extra = self._normalizar_extra(dados_limpos)
            sufixo = self._montar_sufixo(contexto_repr, dados_repr)

        bound_logger = self._logger.bind(
            contexto=contexto_extra or {},
            dados=dados_extra or {},
            suffix=sufixo,
        )
        bound_logger.opt(depth=2).log(nivel_loguru, mensagem)

    def close(self) -> None:
        with self._lock:
            if self._file_sink_id is not None:
                try:
                    _loguru_logger.remove(self._file_sink_id)
                except ValueError:
                    pass
                self._sink_ids = [sid for sid in self._sink_ids if sid != self._file_sink_id]
                self._file_sink_id = None

    @staticmethod
    def formatar_valor(valor: Any) -> str:
        if isinstance(valor, (int, float)):
            return str(valor)
        if isinstance(valor, str):
            if valor.strip() == valor and " " not in valor:
                return valor
            return repr(valor)
        if valor is None:
            return "None"
        return repr(valor)

    @staticmethod
    def _normalizar_extra(valores: Mapping[str, Any]) -> dict[str, Any]:
        normalizado: dict[str, Any] = {}
        for chave, valor in valores.items():
            if isinstance(valor, (str, int, float, bool)) or valor is None:
                normalizado[chave] = valor
            else:
                normalizado[chave] = repr(valor)
        return normalizado

    @staticmethod
    def _montar_sufixo(contexto: Mapping[str, str], dados: Mapping[str, str]) -> str:
        partes: list[str] = []
        if contexto:
            partes.extend(f"{chave}={contexto[chave]}" for chave in sorted(contexto))
        if dados:
            partes.extend(f"{chave}={dados[chave]}" for chave in sorted(dados))
        return "  " + " ".join(partes) if partes else ""

    @staticmethod
    def _resolver_nivel_valor(nivel: str | int) -> int:
        if isinstance(nivel, int):
            return nivel
        chave = str(nivel).lower()
        return _LEVEL_MAP.get(chave, _LEVEL_MAP["info"])

    @staticmethod
    def _resolver_loguru_nome(nivel: str | int) -> str | int:
        if isinstance(nivel, int):
            return nivel
        chave = str(nivel).lower()
        return _LOGURU_NAME_MAP.get(chave, "INFO")

    def _construir_formato_console(self, config: LoggerConfig) -> str:
        partes: list[str] = []
        if config.mostrar_tempo:
            partes.append("<cyan>{time:HH:mm:ss}</cyan>")
        partes.append("<level>{level: <8}</level>")
        partes.append("<level>{message}</level>")
        formato = " | ".join(partes)
        return formato + "{extra[suffix]}"


class ScopedLogger(ILoggingService):
    """Logger derivado que carrega um contexto fixo."""

    def __init__(self, base: FarmLogger, contexto: Mapping[str, Any]) -> None:
        self._base = base
        self._contexto = dict(contexto)

    def com_contexto(self, **dados: Any) -> "ScopedLogger":
        novo = dict(self._contexto)
        for chave, valor in dados.items():
            if valor is not None:
                novo[chave] = valor
        return ScopedLogger(self._base, novo)

    def debug(self, mensagem: str, **dados: Any) -> None:
        self._base.registrar_evento("debug", mensagem, dados, self._contexto)

    def info(self, mensagem: str, **dados: Any) -> None:
        self._base.registrar_evento("info", mensagem, dados, self._contexto)

    def sucesso(self, mensagem: str, **dados: Any) -> None:
        self._base.registrar_evento("sucesso", mensagem, dados, self._contexto)

    def aviso(self, mensagem: str, **dados: Any) -> None:
        self._base.registrar_evento("aviso", mensagem, dados, self._contexto)

    def erro(self, mensagem: str, **dados: Any) -> None:
        self._base.registrar_evento("erro", mensagem, dados, self._contexto)

    def critico(self, mensagem: str, **dados: Any) -> None:
        self._base.registrar_evento("critico", mensagem, dados, self._contexto)

    @contextmanager
    def etapa(
        self,
        titulo: str,
        mensagem_inicial: Optional[str] = None,
        mensagem_sucesso: Optional[str] = None,
        mensagem_falha: Optional[str] = None,
        **dados: Any,
    ):
        dados_limpos = {k: v for k, v in dados.items() if v is not None}
        inicio = mensagem_inicial or f"Iniciando etapa: {titulo}"
        sucesso_msg = mensagem_sucesso or f"Etapa concluida: {titulo}"
        falha_msg = mensagem_falha or f"Falha na etapa: {titulo}"

        self._base.registrar_evento("info", inicio, dados_limpos, self._contexto)
        try:
            yield
        except Exception:
            self._base.registrar_evento("erro", falha_msg, dados_limpos, self._contexto)
            raise
        else:
            self._base.registrar_evento("sucesso", sucesso_msg, dados_limpos, self._contexto)


# Instância global simples -------------------------------------------------

log = FarmLogger()


def configurar_logging(config: Optional[LoggerConfig] = None, **overrides: Any) -> FarmLogger:
    """Configura o logger global e o retorna para encadeamento."""

    final_config = config or LoggerConfig.from_env()
    if overrides:
        final_config = dataclasses.replace(final_config, **overrides)
    log.configure(final_config)
    return log


configurar_logging()

__all__ = ["LoggerConfig", "FarmLogger", "ScopedLogger", "configurar_logging", "log"]
