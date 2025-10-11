"""Sistema avançado de logging com rastreamento completo de erros e finalização forçada."""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
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
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from loguru import logger as _loguru_logger
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.traceback import Traceback as RichTraceback

from raxy.interfaces.services import ILoggingService

# Console do Rich para output formatado
_console = Console(stderr=True, force_terminal=True)

# Mapeamento de níveis
_LEVEL_MAP: dict[str, int] = {
    "trace": 5,
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
    "fatal": 60,
}

_LOGURU_NAME_MAP: dict[str, str] = {
    "trace": "TRACE",
    "debug": "DEBUG",
    "info": "INFO",
    "sucesso": "SUCCESS",
    "success": "SUCCESS",
    "aviso": "WARNING",
    "warning": "WARNING",
    "erro": "ERROR",
    "error": "ERROR",
    "critico": "CRITICAL",
    "critical": "CRITICAL",
    "fatal": "FATAL",
}

# Registrar níveis customizados no loguru
try:
    _loguru_logger.level("SUCESSO")
except ValueError:
    _loguru_logger.level("SUCESSO", no=25, color="<green>", icon="✓")

try:
    _loguru_logger.level("FATAL")
except ValueError:
    _loguru_logger.level("FATAL", no=60, color="<red><bold>", icon="💀")


def _obter_info_chamador(depth: int = 3) -> Dict[str, Any]:
    """Obtém informações detalhadas sobre quem chamou o logger."""
    try:
        frame = inspect.currentframe()
        if frame is None:
            return {}
        
        # Navega pelos frames até encontrar o chamador real
        for _ in range(depth):
            frame = frame.f_back
            if frame is None:
                break
        
        if frame is None:
            return {}
        
        info = inspect.getframeinfo(frame)
        code = frame.f_code
        
        # Tenta obter a classe se existir
        classe = None
        if 'self' in frame.f_locals:
            classe = frame.f_locals['self'].__class__.__name__
        elif 'cls' in frame.f_locals:
            classe = frame.f_locals['cls'].__name__
        
        return {
            "arquivo": Path(info.filename).name,
            "caminho_completo": info.filename,
            "linha": info.lineno,
            "funcao": code.co_name,
            "classe": classe,
            "modulo": inspect.getmodule(frame).__name__ if inspect.getmodule(frame) else None,
        }
    except Exception:
        return {}
    finally:
        del frame


def _formatar_erro_detalhado(
    exc: BaseException,
    tb: TracebackType | None = None,
    contexto: Dict[str, Any] | None = None
) -> str:
    """Formata um erro com todos os detalhes possíveis."""
    lines = []
    
    # Cabeçalho
    lines.append("\n" + "=" * 80)
    lines.append(f"🔴 ERRO CRÍTICO DETECTADO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    lines.append("=" * 80)
    
    # Tipo e mensagem do erro
    lines.append(f"\n📛 Tipo: {exc.__class__.__module__}.{exc.__class__.__name__}")
    lines.append(f"💬 Mensagem: {str(exc)}")
    
    # Contexto adicional
    if contexto:
        lines.append("\n📋 Contexto:")
        for chave, valor in contexto.items():
            lines.append(f"   • {chave}: {valor}")
    
    # Stack trace completo
    lines.append("\n📍 Stack Trace Completo:")
    lines.append("-" * 40)
    
    if tb is None:
        tb = exc.__traceback__
    
    if tb:
        for frame_summary in traceback.extract_tb(tb):
            arquivo = Path(frame_summary.filename).name
            caminho = frame_summary.filename
            linha = frame_summary.lineno
            funcao = frame_summary.name
            codigo = frame_summary.line
            
            lines.append(f"\n  📁 Arquivo: {arquivo}")
            lines.append(f"  📂 Caminho: {caminho}")
            lines.append(f"  📍 Linha: {linha}")
            lines.append(f"  🔧 Função: {funcao}")
            if codigo:
                lines.append(f"  💻 Código: {codigo.strip()}")
    
    # Traceback formatado tradicional
    lines.append("\n" + "─" * 40)
    lines.append("Traceback Formatado:")
    lines.extend(traceback.format_exception(type(exc), exc, tb))
    
    lines.append("=" * 80 + "\n")
    
    return "\n".join(lines)


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
    """Configuração centralizada do sistema de logging."""
    
    nome: str = "raxy"
    nivel_minimo: str | int = "INFO"
    arquivo_log: str | Path | None = None
    sobrescrever_arquivo: bool = False
    mostrar_tempo: bool = True
    mostrar_localizacao: bool = True
    registrar_traceback_rico: bool = True
    usar_cores: bool = True
    rotacao_arquivo: str | int | None = "100 MB"
    retencao_arquivo: str | int | None = "7 days"
    compressao_arquivo: str | None = "zip"
    capturar_excecoes: bool = True
    diretorio_erros: str | Path | None = "error_logs"
    gerar_snapshot_erros: bool = True
    erro_repeticao_limite: int = 3
    erro_repeticao_janela: int = 60
    limite_sufixo: int = 200
    limite_snapshot: int = 10000
    forcar_finalizacao_em_erro: bool = True
    forcar_finalizacao_em_critico: bool = True
    mostrar_thread: bool = True
    mostrar_processo: bool = False
    formato_detalhado: bool = True

    @classmethod
    def from_env(cls) -> "LoggerConfig":
        """Cria a configuração com base nas variáveis de ambiente."""
        cfg = cls()
        
        nivel = os.getenv("LOG_LEVEL")
        if nivel:
            cfg.nivel_minimo = nivel
        
        arquivo = os.getenv("LOG_FILE")
        if arquivo:
            cfg.arquivo_log = arquivo
        
        cfg.sobrescrever_arquivo = _parse_bool(os.getenv("LOG_OVERWRITE"), cfg.sobrescrever_arquivo)
        cfg.mostrar_tempo = _parse_bool(os.getenv("LOG_SHOW_TIME"), cfg.mostrar_tempo)
        cfg.mostrar_localizacao = _parse_bool(os.getenv("LOG_SHOW_LOCATION"), cfg.mostrar_localizacao)
        cfg.usar_cores = _parse_bool(os.getenv("LOG_COLOR"), cfg.usar_cores)
        cfg.registrar_traceback_rico = _parse_bool(
            os.getenv("LOG_RICH_TRACEBACK"), cfg.registrar_traceback_rico
        )
        cfg.forcar_finalizacao_em_erro = _parse_bool(
            os.getenv("LOG_FORCE_EXIT_ON_ERROR"), cfg.forcar_finalizacao_em_erro
        )
        cfg.forcar_finalizacao_em_critico = _parse_bool(
            os.getenv("LOG_FORCE_EXIT_ON_CRITICAL"), cfg.forcar_finalizacao_em_critico
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
        
        return cfg


class FarmLogger(ILoggingService):
    """Sistema de logging avançado com rastreamento completo e finalização forçada."""
    
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
        self._erro_count = 0
        self._critico_count = 0
        self.configure(self._config)

    @property
    def config(self) -> LoggerConfig:
        """Retorna a configuração ativa."""
        return self._config

    def configure(self, config: LoggerConfig) -> None:
        """Aplica uma nova configuração ao logger."""
        with self._lock:
            self._config = config
            self._nivel_minimo = self._resolver_nivel_valor(config.nivel_minimo)
            
            # Remove todos os handlers existentes
            _loguru_logger.remove()
            
            self._sink_ids.clear()
            self._file_sink_id = None
            
            self._logger = _loguru_logger.bind(contexto={}, dados={}, suffix="")
            nivel_loguru = self._resolver_loguru_nome(config.nivel_minimo)
            
            # Formato do console melhorado
            formato_console = self._construir_formato_console(config)
            console_sink_id = _loguru_logger.add(
                sys.stderr,  # Usar stderr para logs
                format=formato_console,
                colorize=config.usar_cores,
                level=nivel_loguru,
                enqueue=False,
                backtrace=config.registrar_traceback_rico,
                diagnose=True,  # Ativar diagnóstico detalhado
            )
            self._sink_ids.append(console_sink_id)
            
            # Configuração de arquivo
            if config.arquivo_log:
                path = Path(config.arquivo_log)
                path.parent.mkdir(parents=True, exist_ok=True)
                
                kwargs: dict[str, Any] = {
                    "level": nivel_loguru,
                    "enqueue": True,
                    "serialize": False,  # Usar formato legível no arquivo
                    "format": self._construir_formato_arquivo(config),
                    "backtrace": config.registrar_traceback_rico,
                    "diagnose": True,
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
            
            # Configuração de diretório de erros
            self._erro_snapshot_dir = Path(config.diretorio_erros).expanduser() if config.diretorio_erros else None
            self._snapshot_error_enabled = bool(self._erro_snapshot_dir and config.gerar_snapshot_erros)
            
            if self._erro_snapshot_dir:
                try:
                    self._erro_snapshot_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    self._snapshot_error_enabled = False
                else:
                    # Arquivo separado para erros críticos
                    error_log_path = self._erro_snapshot_dir / f"{config.nome}_critical_errors.log"
                    error_kwargs: dict[str, Any] = {
                        "level": "ERROR",
                        "enqueue": True,
                        "serialize": False,
                        "format": self._construir_formato_erro(config),
                        "backtrace": True,
                        "diagnose": True,
                        "rotation": "50 MB",
                        "retention": "30 days",
                        "compression": "zip",
                    }
                    
                    error_sink_id = _loguru_logger.add(str(error_log_path), **error_kwargs)
                    self._sink_ids.append(error_sink_id)
            
            self._erros_recentes.clear()
            
            if config.capturar_excecoes:
                self._instalar_tratadores_excecao()
            else:
                self._remover_tratadores_excecao()

    def _construir_formato_console(self, config: LoggerConfig) -> str:
        """Constrói o formato para saída no console."""
        partes: list[str] = []
        
        if config.mostrar_tempo:
            partes.append("<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>")
        
        if config.mostrar_thread:
            partes.append("<dim>[{thread.name}]</dim>")
        
        partes.append("<level>{level: <8}</level>")
        
        if config.mostrar_localizacao:
            partes.append("<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>")
        
        partes.append("<level>{message}</level>")
        
        formato = " | ".join(partes)
        
        # Adiciona informações extras
        formato += "{extra[suffix]}"
        
        return formato

    def _construir_formato_arquivo(self, config: LoggerConfig) -> str:
        """Constrói o formato para saída em arquivo."""
        return (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{thread.name: <12} | "
            "{name}:{function}:{line} | "
            "{message} | "
            "{extra}"
        )

    def _construir_formato_erro(self, config: LoggerConfig) -> str:
        """Constrói o formato especial para arquivo de erros."""
        return (
            f"\n{'='*80}\n"
            "ERRO CRÍTICO - {time:YYYY-MM-DD HH:mm:ss.SSS}\n"
            f"{'='*80}\n"
            "Nível: {level}\n"
            "Thread: {thread.name} (ID: {thread.id})\n"
            "Processo: {process.name} (PID: {process.id})\n"
            "Arquivo: {name}\n"
            "Função: {function}\n"
            "Linha: {line}\n"
            "Mensagem: {message}\n"
            "Contexto: {extra}\n"
            f"{'─'*40}\n"
            "{exception}\n"
            f"{'='*80}\n"
        )

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

    def debug(self, mensagem: str, **dados: Any) -> None:
        self.registrar_evento("debug", mensagem, dados, None)

    def info(self, mensagem: str, **dados: Any) -> None:
        self.registrar_evento("info", mensagem, dados, None)

    def sucesso(self, mensagem: str, **dados: Any) -> None:
        self.registrar_evento("sucesso", mensagem, dados, None)

    def aviso(self, mensagem: str, **dados: Any) -> None:
        self.registrar_evento("aviso", mensagem, dados, None)

    def erro(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro e força finalização se configurado."""
        self._erro_count += 1
        self.registrar_evento("erro", mensagem, dados, None)
        
        if self._config.forcar_finalizacao_em_erro:
            self._forcar_finalizacao(mensagem, dados, "ERRO")

    def critico(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro crítico e força finalização se configurado."""
        self._critico_count += 1
        self.registrar_evento("critico", mensagem, dados, None)
        
        if self._config.forcar_finalizacao_em_critico:
            self._forcar_finalizacao(mensagem, dados, "CRÍTICO")

    def fatal(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro fatal e SEMPRE força finalização."""
        self.registrar_evento("fatal", mensagem, dados, None)
        self._forcar_finalizacao(mensagem, dados, "FATAL")

    def _forcar_finalizacao(self, mensagem: str, dados: Dict[str, Any], nivel: str) -> None:
        """Força a finalização do programa após um erro crítico."""
        info_chamador = _obter_info_chamador(4)
        
        # Criar painel de erro visível
        _console.print("\n")
        
        # Criar tabela com informações do erro
        table = Table(title=f"💀 {nivel} - FINALIZANDO APLICAÇÃO", show_header=True, header_style="bold red")
        table.add_column("Campo", style="cyan", width=20)
        table.add_column("Valor", style="white")
        
        table.add_row("Mensagem", mensagem)
        table.add_row("Arquivo", info_chamador.get("arquivo", "N/A"))
        table.add_row("Caminho", info_chamador.get("caminho_completo", "N/A"))
        table.add_row("Linha", str(info_chamador.get("linha", "N/A")))
        table.add_row("Função", info_chamador.get("funcao", "N/A"))
        if info_chamador.get("classe"):
            table.add_row("Classe", info_chamador["classe"])
        table.add_row("Thread", threading.current_thread().name)
        table.add_row("PID", str(os.getpid()))
        
        # Adicionar dados extras
        for chave, valor in dados.items():
            if chave not in ["erro", "traceback", "exc_info"]:
                table.add_row(chave.capitalize(), str(valor)[:100])
        
        _console.print(table)
        
        # Se houver exceção, mostrar traceback formatado
        if "erro" in dados and isinstance(dados["erro"], BaseException):
            _console.print("\n")
            _console.print(Panel(
                RichTraceback.from_exception(
                    type(dados["erro"]),
                    dados["erro"],
                    dados["erro"].__traceback__
                ),
                title="Stack Trace",
                border_style="red"
            ))
        
        # Salvar snapshot antes de finalizar
        if self._snapshot_error_enabled:
            self._salvar_snapshot_finalizacao(nivel, mensagem, dados, info_chamador)
        
        # Aguardar um momento para garantir que tudo foi escrito
        time.sleep(0.5)
        
        # FORÇAR FINALIZAÇÃO
        _console.print(f"\n[bold red]❌ APLICAÇÃO FINALIZADA DEVIDO A {nivel}[/bold red]\n")
        sys.exit(1)

    def _salvar_snapshot_finalizacao(
        self, 
        nivel: str, 
        mensagem: str, 
        dados: Dict[str, Any], 
        info_chamador: Dict[str, Any]
    ) -> None:
        """Salva um snapshot detalhado antes da finalização."""
        if not self._erro_snapshot_dir:
            return
        
        timestamp = datetime.now()
        snapshot = {
            "timestamp": timestamp.isoformat(),
            "nivel": nivel,
            "mensagem": mensagem,
            "localizacao": info_chamador,
            "dados": {k: str(v)[:1000] for k, v in dados.items()},
            "contexto": self._contexto_padrao,
            "thread": {
                "name": threading.current_thread().name,
                "id": threading.current_thread().ident,
                "daemon": threading.current_thread().daemon,
            },
            "processo": {
                "pid": os.getpid(),
                "cwd": os.getcwd(),
            },
            "contadores": {
                "erros": self._erro_count,
                "criticos": self._critico_count,
            }
        }
        
        # Se houver exceção, adicionar traceback completo
        if "erro" in dados and isinstance(dados["erro"], BaseException):
            exc = dados["erro"]
            snapshot["excecao"] = {
                "tipo": f"{exc.__class__.__module__}.{exc.__class__.__name__}",
                "mensagem": str(exc),
                "traceback": traceback.format_exception(type(exc), exc, exc.__traceback__)
            }
        
        # Salvar em arquivo JSON
        nome_arquivo = f"crash_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.json"
        caminho_arquivo = self._erro_snapshot_dir / nome_arquivo
        
        try:
            with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False, default=str)
            print(f"Snapshot salvo em: {caminho_arquivo}", file=sys.stderr)
        except Exception as e:
            print(f"Erro ao salvar snapshot: {e}", file=sys.stderr)

    @contextmanager
    def etapa(
        self,
        titulo: str,
        mensagem_inicial: Optional[str] = None,
        mensagem_sucesso: Optional[str] = None,
        mensagem_falha: Optional[str] = None,
        **dados: Any,
    ):
        """Context manager para rastrear etapas de execução."""
        dados_limpos = {k: v for k, v in dados.items() if v is not None}
        inicio = mensagem_inicial or f"Iniciando etapa: {titulo}"
        sucesso_msg = mensagem_sucesso or f"Etapa concluída: {titulo}"
        falha_msg = mensagem_falha or f"Falha na etapa: {titulo}"
        
        self.registrar_evento("info", inicio, dados_limpos, None)
        try:
            yield
        except Exception as exc:
            # Adicionar a exceção aos dados para rastreamento
            dados_limpos["erro"] = exc
            dados_limpos["traceback"] = traceback.format_exc()
            self.registrar_evento("erro", falha_msg, dados_limpos, None)
            raise
        else:
            self.registrar_evento("sucesso", sucesso_msg, dados_limpos, None)

    def deve_emitir(self, nivel: str | int) -> bool:
        """Verifica se o nível deve ser emitido."""
        valor = self._resolver_nivel_valor(nivel)
        return valor >= self._nivel_minimo

    def registrar_evento(
        self,
        nivel: str | int,
        mensagem: str,
        dados: Mapping[str, Any] | None,
        contexto_extra: Optional[Mapping[str, Any]],
    ) -> None:
        """Registra um evento de log com informações detalhadas."""
        if not self.deve_emitir(nivel):
            return
        
        # Obter informações do chamador
        info_chamador = _obter_info_chamador(3)
        
        dados_limpos = {k: v for k, v in (dados or {}).items() if v is not None}
        
        # Adicionar informações de localização aos dados
        if self._config.mostrar_localizacao:
            dados_limpos.update({
                "_arquivo": info_chamador.get("arquivo"),
                "_linha": info_chamador.get("linha"),
                "_funcao": info_chamador.get("funcao"),
            })
            if info_chamador.get("classe"):
                dados_limpos["_classe"] = info_chamador["classe"]
        
        excecao_capturada: BaseException | None = None
        excecao_traceback: TracebackType | None = None
        
        # Processar exceções nos dados
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
        
        # Verificar por traceback em string
        if "traceback" not in dados_limpos:
            for chave in ("erro", "error", "exception"):
                valor = dados_limpos.get(chave)
                if isinstance(valor, str) and "Traceback (most recent call last)" in valor:
                    dados_limpos["traceback"] = valor
                    break
        
        # Processar exc_info
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
            
            # Criar sufixo com informações importantes
            dados_para_sufixo = self._limitar_para_sufixo(dados_textual, self._config.limite_sufixo)
            sufixo = self._montar_sufixo(contexto_textual, dados_para_sufixo)
        
        opt_kwargs: dict[str, Any] = {"depth": 3}
        if excecao_capturada is not None:
            opt_kwargs["exception"] = excecao_capturada
        
        bound_logger = self._logger.bind(
            contexto=contexto_normalizado or {},
            dados=dados_normalizado or {},
            suffix=sufixo,
        )
        
        # Adicionar marcador visual para erros
        if valor_nivel >= _LEVEL_MAP["erro"]:
            mensagem = f"❌ {mensagem}"
        elif valor_nivel >= _LEVEL_MAP["aviso"]:
            mensagem = f"⚠️  {mensagem}"
        elif nivel == "sucesso":
            mensagem = f"✅ {mensagem}"
        
        bound_logger.opt(**opt_kwargs).log(nivel_loguru, mensagem)
        
        # Processar erro se necessário
        traceback_texto: Optional[str] = None
        if excecao_capturada is not None:
            traceback_texto = "".join(
                traceback.format_exception(
                    type(excecao_capturada),
                    excecao_capturada,
                    excecao_traceback or excecao_capturada.__traceback__,
                )
            )
            
            # Mostrar erro detalhado no console para níveis ERROR e acima
            if valor_nivel >= _LEVEL_MAP["erro"] and self._config.formato_detalhado:
                erro_formatado = _formatar_erro_detalhado(
                    excecao_capturada,
                    excecao_traceback,
                    {**contexto_textual, **dados_textual}
                )
                print(erro_formatado, file=sys.stderr)
        else:
            tb_value = dados_limpos.get("traceback")
            if isinstance(tb_value, str):
                traceback_texto = tb_value
        
        # Pós-processamento para erros
        if valor_nivel >= _LEVEL_MAP["erro"]:
            self._apos_registrar_erro(
                mensagem,
                nivel_loguru,
                contexto_textual,
                dados_textual,
                excecao_capturada,
                traceback_texto,
                info_chamador,
            )

    def close(self) -> None:
        """Fecha o logger e libera recursos."""
        with self._lock:
            if self._file_sink_id is not None:
                try:
                    _loguru_logger.remove(self._file_sink_id)
                except ValueError:
                    pass
                self._file_sink_id = None

    @staticmethod
    def formatar_valor(valor: Any) -> str:
        """Formata um valor para exibição."""
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
        """Normaliza valores extras para serem serializáveis."""
        normalizado: dict[str, Any] = {}
        for chave, valor in valores.items():
            if isinstance(valor, (str, int, float, bool)) or valor is None:
                normalizado[chave] = valor
            else:
                normalizado[chave] = repr(valor)
        return normalizado

    @staticmethod
    def _stringify_map(valores: Mapping[str, Any]) -> dict[str, str]:
        """Converte todos os valores para string."""
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
        """Monta o sufixo com informações adicionais."""
        partes: list[str] = []
        
        # Priorizar informações de localização
        for chave in ["_arquivo", "_linha", "_funcao", "_classe"]:
            if chave in dados:
                valor = dados[chave]
                if valor and valor != "None":
                    if chave == "_arquivo":
                        partes.append(f"📁 {valor}")
                    elif chave == "_linha":
                        partes.append(f"L{valor}")
                    elif chave == "_funcao":
                        partes.append(f"fn:{valor}")
                    elif chave == "_classe":
                        partes.append(f"cls:{valor}")
        
        # Adicionar contexto
        for chave in sorted(contexto):
            if not chave.startswith("_"):
                valor = contexto[chave]
                if valor:
                    partes.append(f"{chave}={valor}")
        
        # Adicionar dados (exceto os de localização)
        for chave in sorted(dados):
            if not chave.startswith("_") and chave not in ["traceback", "exc_info"]:
                valor = dados[chave]
                if valor and len(valor) < 50:
                    partes.append(f"{chave}={valor}")
        
        return "  " + " | ".join(partes) if partes else ""

    @staticmethod
    def _limitar_para_sufixo(dados: Mapping[str, str], limite: int) -> dict[str, str]:
        """Limita o tamanho dos valores para o sufixo."""
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
        """Limita o tamanho dos valores para snapshot."""
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
        """Gera uma assinatura única para um erro."""
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
        """Monitora erros repetidos e alerta quando necessário."""
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
            self.registrar_evento("aviso", "⚠️  Erro recorrente detectado", alerta_dados, contexto_textual)
            
            # Se muitos erros repetidos, considerar finalização
            if len(timestamps) >= limite * 2:
                self.registrar_evento(
                    "critico", 
                    f"Muitos erros repetidos ({len(timestamps)} em {janela}s)", 
                    alerta_dados, 
                    contexto_textual
                )
            
            timestamps.clear()

    def _registrar_snapshot_erro(
        self,
        mensagem: str,
        nivel: str | int,
        contexto_textual: Mapping[str, str],
        dados_textual: Mapping[str, str],
        excecao: BaseException | None,
        traceback_texto: Optional[str],
        info_chamador: Dict[str, Any],
    ) -> None:
        """Registra um snapshot detalhado do erro."""
        if not self._snapshot_error_enabled or not self._erro_snapshot_dir:
            return
        
        agora = datetime.utcnow()
        payload = {
            "timestamp": agora.isoformat() + "Z",
            "mensagem": mensagem,
            "nivel": nivel if isinstance(nivel, str) else str(nivel),
            "localizacao": info_chamador,
            "contexto": self._limitar_para_snapshot(contexto_textual, self._config.limite_snapshot),
            "dados": self._limitar_para_snapshot(dados_textual, self._config.limite_snapshot),
            "thread": threading.current_thread().name,
            "processo": os.getpid(),
        }
        if excecao is not None:
            payload["excecao"] = {
                "tipo": f"{excecao.__class__.__module__}.{excecao.__class__.__name__}",
                "mensagem": str(excecao),
            }
        if traceback_texto:
            payload["traceback"] = traceback_texto
        
        nome_arquivo = (
            f"{self._config.nome}_{agora.strftime('%Y-%m-%d_%H-%M-%S_%f')}_{uuid.uuid4().hex[:8]}.json"
        )
        try:
            self._erro_snapshot_dir.mkdir(parents=True, exist_ok=True)
            (self._erro_snapshot_dir / nome_arquivo).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
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
        info_chamador: Dict[str, Any],
    ) -> None:
        """Ações a serem executadas após registrar um erro."""
        self._registrar_snapshot_erro(
            mensagem, nivel, contexto_textual, dados_textual, 
            excecao, traceback_texto, info_chamador
        )
        self._monitorar_erros_repetidos(mensagem, contexto_textual, dados_textual)

    def _instalar_tratadores_excecao(self) -> None:
        """Instala tratadores globais para exceções não capturadas."""
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
        """Remove os tratadores globais de exceção."""
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
        """Registra uma exceção não tratada."""
        if excecao is None or isinstance(excecao, (SystemExit, KeyboardInterrupt)):
            return
        try:
            stack = "".join(traceback.format_exception(type(excecao), excecao, tb or excecao.__traceback__))
            self.fatal(
                "💀 Exceção não tratada capturada",
                excecao=excecao,
                traceback=stack,
                thread=threading.current_thread().name,
            )
        except Exception:
            pass

    @staticmethod
    def _resolver_nivel_valor(nivel: str | int) -> int:
        """Resolve o valor numérico de um nível."""
        if isinstance(nivel, int):
            return nivel
        chave = str(nivel).lower()
        return _LEVEL_MAP.get(chave, _LEVEL_MAP["info"])

    @staticmethod
    def _resolver_loguru_nome(nivel: str | int) -> str | int:
        """Resolve o nome do nível para o loguru."""
        if isinstance(nivel, int):
            return nivel
        chave = str(nivel).lower()
        return _LOGURU_NAME_MAP.get(chave, "INFO")


class ScopedLogger(ILoggingService):
    """Logger derivado que carrega um contexto fixo."""
    
    def __init__(self, base: FarmLogger, contexto: Mapping[str, Any]) -> None:
        self._base = base
        self._contexto = dict(contexto)

    def com_contexto(self, **dados: Any) -> "ScopedLogger":
        """Cria um novo logger com contexto adicional."""
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
        """Registra um erro com contexto."""
        self._base.registrar_evento("erro", mensagem, dados, self._contexto)

    def critico(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro crítico com contexto."""
        self._base.registrar_evento("critico", mensagem, dados, self._contexto)

    def fatal(self, mensagem: str, **dados: Any) -> None:
        """Registra um erro fatal com contexto."""
        self._base.registrar_evento("fatal", mensagem, dados, self._contexto)

    @contextmanager
    def etapa(
        self,
        titulo: str,
        mensagem_inicial: Optional[str] = None,
        mensagem_sucesso: Optional[str] = None,
        mensagem_falha: Optional[str] = None,
        **dados: Any,
    ):
        """Context manager para rastrear etapas com contexto."""
        dados_limpos = {k: v for k, v in dados.items() if v is not None}
        inicio = mensagem_inicial or f"Iniciando etapa: {titulo}"
        sucesso_msg = mensagem_sucesso or f"Etapa concluída: {titulo}"
        falha_msg = mensagem_falha or f"Falha na etapa: {titulo}"
        
        self._base.registrar_evento("info", inicio, dados_limpos, self._contexto)
        try:
            yield
        except Exception as exc:
            dados_limpos["erro"] = exc
            dados_limpos["traceback"] = traceback.format_exc()
            self._base.registrar_evento("erro", falha_msg, dados_limpos, self._contexto)
            raise
        else:
            self._base.registrar_evento("sucesso", sucesso_msg, dados_limpos, self._contexto)


# Instância global do logger
log = FarmLogger()


def configurar_logging(config: Optional[LoggerConfig] = None, **overrides: Any) -> FarmLogger:
    """Configura o logger global e o retorna para encadeamento."""
    final_config = config or LoggerConfig.from_env()
    if overrides:
        final_config = dataclasses.replace(final_config, **overrides)
    log.configure(final_config)
    return log


# Configurar com valores padrão na importação
configurar_logging()

__all__ = ["LoggerConfig", "FarmLogger", "ScopedLogger", "configurar_logging", "log"]