"""Camada de logging baseada em Loguru com API em portugues.

Esta versao oferece recurso de contexto, capturas estruturadas de erros e
alerta para falhas recorrentes, ideal para automacoes.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sys
import threading
import time
import traceback
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Mapping, Optional

from loguru import logger as _loguru_logger

from raxy.interfaces.services import ILoggingService


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


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    texto = value.strip().lower()
    if not texto:
        return default
    return texto in {"1", "true", "t", "yes", "y", "on"}


def _parse_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    texto = value.strip()
    if not texto:
        return default
    try:
        return int(texto)
    except ValueError:
        return default


@dataclass(slots=True)
class LoggerConfig:
    """Configuracao centralizada do logger.

    O comportamento padrao privilegia a saida em console com cores, mas o
    servico suporta escrita em arquivo rotacionado, capturas extras e ajustes
    via variaveis de ambiente. Manter os nomes em portugues facilita a leitura
    e manutencao para o time.
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
    capturar_excecoes: bool = True
    diretorio_erros: str | Path | None = "error_logs"
    gerar_snapshot_erros: bool = True
    erro_repeticao_limite: int = 5
    erro_repeticao_janela: int = 300
    limite_sufixo: int = 160
    limite_snapshot: int = 4000

    @classmethod
    def from_env(cls) -> "LoggerConfig":
        """Cria a configuracao com base nas variaveis de ambiente."""

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

        cfg.capturar_excecoes = _parse_bool(
            os.getenv("LOG_CAPTURE_UNHANDLED"), cfg.capturar_excecoes
        )

        diretorio_erros = os.getenv("LOG_ERROR_DIR")
        if diretorio_erros is not None:
            diretorio_erros = diretorio_erros.strip()
            cfg.diretorio_erros = diretorio_erros or None

        cfg.gerar_snapshot_erros = _parse_bool(
            os.getenv("LOG_ERROR_SNAPSHOT"), cfg.gerar_snapshot_erros
        )

        repeticao_limite = os.getenv("LOG_ERROR_REPEAT_THRESHOLD")
        if repeticao_limite is not None:
            cfg.erro_repeticao_limite = max(0, _parse_int(repeticao_limite, cfg.erro_repeticao_limite))

        repeticao_janela = os.getenv("LOG_ERROR_REPEAT_WINDOW")
        if repeticao_janela is not None:
            cfg.erro_repeticao_janela = max(1, _parse_int(repeticao_janela, cfg.erro_repeticao_janela))

        limite_sufixo = os.getenv("LOG_SUFFIX_LIMIT")
        if limite_sufixo is not None:
            cfg.limite_sufixo = max(20, _parse_int(limite_sufixo, cfg.limite_sufixo))

        limite_snapshot = os.getenv("LOG_ERROR_SNAPSHOT_LIMIT")
        if limite_snapshot is not None:
            cfg.limite_snapshot = max(100, _parse_int(limite_snapshot, cfg.limite_snapshot))

        return cfg


class FarmLogger(ILoggingService):
    """Implementacao principal do logger com API em portugues."""

    def __init__(self) -> None:
        self._config = LoggerConfig()
        self._nivel_minimo = self._resolver_nivel_valor(self._config.nivel_minimo)
        self._contexto_padrao: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._sink_ids: list[int] = []
        self._file_sink_id: Optional[int] = None
        self._logger = _loguru_logger.bind(contexto={}, dados={}, suffix="")
        self._erro_snapshot_dir: Optional[Path] = None
        self._snapshot_error_enabled = False
        self._erros_recentes: dict[str, dict[str, Any]] = {}
        self._novo_excepthook: Optional[Callable[..., Any]] = None
        self._excepthook_original: Optional[Callable[..., Any]] = None
        self._novo_thread_excepthook: Optional[Callable[..., Any]] = None
        self._thread_excepthook_original: Optional[Callable[..., Any]] = None
        self.configure(self._config)

    @property
    def config(self) -> LoggerConfig:
        """Retorna a configuracao ativa para inspecao."""

        return self._config

    def configure(self, config: LoggerConfig) -> None:
        """Aplica uma nova configuracao ao logger."""

        with self._lock:
            self._config = config
            self._nivel_minimo = self._resolver_nivel_valor(config.nivel_minimo)

            # Remove todos os handlers existentes para evitar duplicatas
            _loguru_logger.remove()

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
                    "serialize": True,
                    "backtrace": config.registrar_traceback_rico,
                    "diagnose": False,
                    "mode": "w" if config.sobrescrever_arquivo else "a",
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

            self._erro_snapshot_dir = Path(config.diretorio_erros).expanduser() if config.diretorio_erros else None
            self._snapshot_error_enabled = bool(self._erro_snapshot_dir and config.gerar_snapshot_erros)

            if self._erro_snapshot_dir:
                try:
                    self._erro_snapshot_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    self._snapshot_error_enabled = False
                else:
                    error_log_path = self._erro_snapshot_dir / f"{config.nome}_errors.jsonl"
                    error_kwargs: dict[str, Any] = {
                        "level": "ERROR",
                        "enqueue": True,
                        "serialize": True,
                        "backtrace": config.registrar_traceback_rico,
                        "diagnose": False,
                    }
                    if config.rotacao_arquivo is not None:
                        error_kwargs["rotation"] = config.rotacao_arquivo
                    else:
                        error_kwargs["rotation"] = "1 day"
                    if config.retencao_arquivo is not None:
                        error_kwargs["retention"] = config.retencao_arquivo
                    if config.compressao_arquivo is not None:
                        error_kwargs["compression"] = config.compressao_arquivo

                    error_sink_id = _loguru_logger.add(str(error_log_path), **error_kwargs)
                    self._sink_ids.append(error_sink_id)

            self._erros_recentes.clear()

            if config.capturar_excecoes:
                self._instalar_tratadores_excecao()
            else:
                self._remover_tratadores_excecao()

    def atualizar_contexto_padrao(self, **dados: Any) -> None:
        """Adiciona ou atualiza campos que aparecem em todos os logs."""

        with self._lock:
            filtrados = {k: v for k, v in dados.items() if v is not None}
            self._contexto_padrao.update(filtrados)

    def limpar_contexto_padrao(self, *chaves: str) -> None:
        """Remove campos do contexto padrao."""

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

    def deve_emitir(self, nivel: str | int) -> bool:
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

        excecao_capturada: BaseException | None = None
        excecao_traceback: TracebackType | None = None

        for chave, valor in list(dados_limpos.items()):
            if isinstance(valor, BaseException):
                excecao_capturada = valor
                excecao_traceback = valor.__traceback__
                dados_limpos[chave] = repr(valor)
            elif isinstance(valor, tuple) and len(valor) == 3 and isinstance(valor[1], BaseException):
                excecao_capturada = valor[1]
                if isinstance(valor[2], TracebackType):
                    excecao_traceback = valor[2]
                dados_limpos[chave] = repr(valor[1])

        if "traceback" not in dados_limpos:
            for chave in ("erro", "error", "exception"):
                valor = dados_limpos.get(chave)
                if isinstance(valor, str) and "Traceback (most recent call last)" in valor:
                    dados_limpos["traceback"] = valor
                    break

        exc_info_val = dados_limpos.get("exc_info")
        if excecao_capturada is None:
            if isinstance(exc_info_val, tuple) and len(exc_info_val) == 3 and isinstance(exc_info_val[1], BaseException):
                excecao_capturada = exc_info_val[1]
                if isinstance(exc_info_val[2], TracebackType):
                    excecao_traceback = exc_info_val[2]
                dados_limpos["exc_info"] = repr(exc_info_val[1])
            elif exc_info_val in {True, 1}:
                tipo_atual, excecao_atual, traceback_atual = sys.exc_info()
                if isinstance(excecao_atual, BaseException):
                    excecao_capturada = excecao_atual
                    excecao_traceback = traceback_atual
                dados_limpos["exc_info"] = bool(exc_info_val)

        valor_nivel = self._resolver_nivel_valor(nivel)
        nivel_loguru = self._resolver_loguru_nome(nivel)

        with self._lock:
            contexto = dict(self._contexto_padrao)
            if contexto_extra:
                for chave, valor in contexto_extra.items():
                    if valor is not None:
                        contexto[chave] = valor

            contexto_normalizado = self._normalizar_extra(contexto)
            dados_normalizado = self._normalizar_extra(dados_limpos)

            contexto_textual = self._stringify_map(contexto_normalizado)
            dados_textual = self._stringify_map(dados_normalizado)

            dados_para_sufixo = self._limitar_para_sufixo(dados_textual, self._config.limite_sufixo)
            sufixo = self._montar_sufixo(contexto_textual, dados_para_sufixo)

        opt_kwargs: dict[str, Any] = {"depth": 2}
        if excecao_capturada is not None:
            opt_kwargs["exception"] = excecao_capturada

        bound_logger = self._logger.bind(
            contexto=contexto_normalizado or {},
            dados=dados_normalizado or {},
            suffix=sufixo,
        )
        bound_logger.opt(**opt_kwargs).log(nivel_loguru, mensagem)

        traceback_texto: Optional[str] = None
        if excecao_capturada is not None:
            traceback_texto = "".join(
                traceback.format_exception(
                    type(excecao_capturada),
                    excecao_capturada,
                    excecao_traceback or excecao_capturada.__traceback__,
                )
            )
        else:
            tb_value = dados_limpos.get("traceback")
            if isinstance(tb_value, str):
                traceback_texto = tb_value

        if valor_nivel >= _LEVEL_MAP["erro"]:
            self._apos_registrar_erro(
                mensagem,
                nivel_loguru,
                contexto_textual,
                dados_textual,
                excecao_capturada,
                traceback_texto,
            )

    def close(self) -> None:
        with self._lock:
            if self._file_sink_id is not None:
                try:
                    _loguru_logger.remove(self._file_sink_id)
                except ValueError:
                    pass
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
    def _stringify_map(valores: Mapping[str, Any]) -> dict[str, str]:
        retorno: dict[str, str] = {}
        for chave in valores:
            valor = valores[chave]
            if isinstance(valor, str):
                retorno[chave] = valor
            else:
                retorno[chave] = repr(valor)
        return retorno

    @staticmethod
    def _montar_sufixo(contexto: Mapping[str, str], dados: Mapping[str, str]) -> str:
        partes: list[str] = []
        for chave in sorted(contexto):
            valor = contexto[chave]
            if valor:
                partes.append(f"{chave}={valor}")
        for chave in sorted(dados):
            valor = dados[chave]
            if valor:
                partes.append(f"{chave}={valor}")
        return "  " + " ".join(partes) if partes else ""

    @staticmethod
    def _limitar_para_sufixo(dados: Mapping[str, str], limite: int) -> dict[str, str]:
        if limite <= 0:
            return {}
        resultado: dict[str, str] = {}
        for chave in sorted(dados):
            valor = dados[chave]
            if not valor or chave == "traceback" or "\n" in valor:
                continue
            if len(valor) > limite:
                resultado[chave] = valor[: max(3, limite - 3)] + "..."
            else:
                resultado[chave] = valor
        return resultado

    @staticmethod
    def _limitar_para_snapshot(dados: Mapping[str, str], limite: int) -> dict[str, str]:
        max_len = max(32, limite)
        retorno: dict[str, str] = {}
        for chave in sorted(dados):
            valor = dados[chave]
            if len(valor) > max_len:
                retorno[chave] = valor[: max_len - 3] + "..."
            else:
                retorno[chave] = valor
        return retorno

    def _gerar_assinatura_erro(
        self,
        mensagem: str,
        contexto: Mapping[str, str],
        dados: Mapping[str, str],
    ) -> str:
        contexto_compacto = self._limitar_para_snapshot(contexto, 256)
        dados_sem_trace = {k: dados[k] for k in dados if k not in {"traceback", "exc_info"}}
        dados_compacto = self._limitar_para_snapshot(dados_sem_trace, 256)
        estrutura = {
            "mensagem": mensagem,
            "contexto": contexto_compacto,
            "dados": dados_compacto,
        }
        bruto = json.dumps(estrutura, sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(bruto.encode("utf-8", "ignore")).hexdigest()

    def _monitorar_erros_repetidos(
        self,
        mensagem: str,
        contexto_textual: Mapping[str, str],
        dados_textual: Mapping[str, str],
    ) -> None:
        limite = max(0, self._config.erro_repeticao_limite)
        if limite < 2:
            return
        janela = max(1, self._config.erro_repeticao_janela)
        assinatura = self._gerar_assinatura_erro(mensagem, contexto_textual, dados_textual)

        if assinatura not in self._erros_recentes and len(self._erros_recentes) >= 1024:
            chave_antiga = next(iter(self._erros_recentes))
            self._erros_recentes.pop(chave_antiga, None)

        registro = self._erros_recentes.setdefault(
            assinatura,
            {"timestamps": deque(), "mensagem": mensagem, "contexto": contexto_textual, "dados": dados_textual},
        )
        timestamps: deque[float] = registro["timestamps"]
        agora = time.time()
        timestamps.append(agora)
        while timestamps and agora - timestamps[0] > janela:
            timestamps.popleft()

        registro["mensagem"] = mensagem
        registro["contexto"] = contexto_textual
        registro["dados"] = dados_textual

        if len(timestamps) >= limite:
            alerta_dados = {
                "mensagem_original": mensagem,
                "ocorrencias": len(timestamps),
                "janela_segundos": janela,
                "assinatura": assinatura[:12],
            }
            self.registrar_evento("aviso", "Erro recorrente detectado", alerta_dados, contexto_textual)
            timestamps.clear()

    def _registrar_snapshot_erro(
        self,
        mensagem: str,
        nivel: str | int,
        contexto_textual: Mapping[str, str],
        dados_textual: Mapping[str, str],
        excecao: BaseException | None,
        traceback_texto: Optional[str],
    ) -> None:
        if not self._snapshot_error_enabled or not self._erro_snapshot_dir:
            return

        agora = datetime.utcnow()
        payload = {
            "timestamp": agora.isoformat() + "Z",
            "mensagem": mensagem,
            "nivel": nivel if isinstance(nivel, str) else str(nivel),
            "contexto": self._limitar_para_snapshot(contexto_textual, self._config.limite_snapshot),
            "dados": self._limitar_para_snapshot(dados_textual, self._config.limite_snapshot),
        }
        if excecao is not None:
            payload["excecao"] = repr(excecao)
        if traceback_texto:
            payload["traceback"] = traceback_texto

        nome_arquivo = (
            f"{self._config.nome}_{agora.strftime('%Y-%m-%d_%H-%M-%S_%f')}_{uuid.uuid4().hex[:8]}.json"
        )
        try:
            self._erro_snapshot_dir.mkdir(parents=True, exist_ok=True)
            (self._erro_snapshot_dir / nome_arquivo).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _apos_registrar_erro(
        self,
        mensagem: str,
        nivel: str | int,
        contexto_textual: Mapping[str, str],
        dados_textual: Mapping[str, str],
        excecao: BaseException | None,
        traceback_texto: Optional[str],
    ) -> None:
        self._registrar_snapshot_erro(mensagem, nivel, contexto_textual, dados_textual, excecao, traceback_texto)
        self._monitorar_erros_repetidos(mensagem, contexto_textual, dados_textual)

    def _instalar_tratadores_excecao(self) -> None:
        if self._novo_excepthook is not None:
            return

        self._excepthook_original = sys.excepthook

        def excepthook(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
            self._registrar_excecao_nao_tratada(exc, tb)
            if self._excepthook_original and self._excepthook_original is not excepthook:
                try:
                    self._excepthook_original(exc_type, exc, tb)
                except Exception:
                    pass

        self._novo_excepthook = excepthook
        sys.excepthook = excepthook

        if hasattr(threading, "excepthook"):
            self._thread_excepthook_original = threading.excepthook

            def thread_hook(args: Any) -> None:
                exc_value = getattr(args, "exc_value", None)
                exc_traceback = getattr(args, "exc_traceback", None)
                if isinstance(exc_value, BaseException):
                    self._registrar_excecao_nao_tratada(exc_value, exc_traceback)
                original = self._thread_excepthook_original
                if original and original is not thread_hook:
                    try:
                        original(args)
                    except Exception:
                        pass

            self._novo_thread_excepthook = thread_hook
            threading.excepthook = thread_hook
        else:
            self._thread_excepthook_original = None
            self._novo_thread_excepthook = None

    def _remover_tratadores_excecao(self) -> None:
        if self._novo_excepthook and sys.excepthook is self._novo_excepthook:
            sys.excepthook = self._excepthook_original or sys.__excepthook__
        self._novo_excepthook = None
        self._excepthook_original = None

        if (
            self._novo_thread_excepthook
            and hasattr(threading, "excepthook")
            and threading.excepthook is self._novo_thread_excepthook
        ):
            if self._thread_excepthook_original:
                threading.excepthook = self._thread_excepthook_original
        self._novo_thread_excepthook = None
        self._thread_excepthook_original = None

    def _registrar_excecao_nao_tratada(
        self,
        excecao: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if excecao is None or isinstance(excecao, (SystemExit, KeyboardInterrupt)):
            return
        try:
            stack = "".join(traceback.format_exception(type(excecao), excecao, tb or excecao.__traceback__))
            self.critico(
                "Excecao nao tratada capturada",
                excecao=excecao,
                traceback=stack,
                thread=threading.current_thread().name,
            )
        except Exception:
            pass

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
            partes.append("<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>")
        partes.append("<level>{level: <8}</level>")
        partes.append("<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
        formato = " | ".join(partes)
        # O sufixo é tratado pelo loguru automaticamente através do `bind`
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