"""Camada de logging opinativa para os fluxos da aplicacao.

A ideia e oferecer uma interface simples, toda em portugues, mas que cubra
os casos mais comuns de automacoes: logs coloridos no terminal, opcao de
escrita em arquivo, contexto dinamico e uma API amigavel estilo framework.

Uso tipico::

    from resources.logging import configurar_logging, log

    configurar_logging()  # opcional: respeita variaveis de ambiente
    log.info("Aplicacao iniciada", arquivo="users.txt")

    with log.etapa("Login das contas", contas=10):
        ...  # codigo pode levantar excecoes normalmente

    conta_logger = log.com_contexto(conta="alice@example.com")
    conta_logger.sucesso("Login concluido")

Toda a documentacao publica esta em portugues para facilitar a manutencao.
"""

from __future__ import annotations

import atexit
import dataclasses
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from rich.console import Console
from rich.theme import Theme
from rich.text import Text
from rich.traceback import install as install_rich_traceback

# Mapas auxiliares ---------------------------------------------------------

_LEVEL_MAP: Dict[str, int] = {
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

_NORMALIZED_NAMES = {
    "debug": "debug",
    "info": "info",
    "sucesso": "sucesso",
    "success": "sucesso",
    "aviso": "aviso",
    "warning": "aviso",
    "erro": "erro",
    "error": "erro",
    "critico": "critico",
    "critical": "critico",
}

_DEFAULT_THEME = Theme(
    {
        "log.time": "cyan dim",
        "log.debug": "dim",
        "log.info": "white",
        "log.sucesso": "bold green",
        "log.aviso": "yellow",
        "log.erro": "bold red",
        "log.critico": "white on red",
        "log.contexto": "bright_black",
    }
)

_TRACEBACK_INSTALADO = False


def _normalizar_nivel(nome: str) -> str:
    chave = nome.lower()
    return _NORMALIZED_NAMES.get(chave, "info")


def _resolver_nivel(valor: str | int) -> int:
    if isinstance(valor, int):
        return valor
    chave = valor.lower()
    return _LEVEL_MAP.get(chave, _LEVEL_MAP["info"])


def _env_flag(nome: str) -> Optional[bool]:
    valor = os.getenv(nome)
    if valor is None:
        return None
    valor = valor.strip().lower()
    if not valor:
        return None
    if valor in {"1", "true", "sim", "yes", "on"}:
        return True
    if valor in {"0", "false", "nao", "no", "off"}:
        return False
    return None


@dataclass(slots=True)
class LoggerConfig:
    """Configuracao centralizada do logger.

    Todos os campos possuem valores padrao seguros para uso local, mas podem
    ser sobrescritos via parametros ou variaveis de ambiente.

    A traducao intencional dos atributos garante que quem esta lendo o codigo
    entenda rapidamente a intencao sem precisar misturar ingles/portugues.
    """

    nome: str = "farm"
    nivel_minimo: str | int = "INFO"
    arquivo_log: str | Path | None = None
    sobrescrever_arquivo: bool = False
    mostrar_tempo: bool = True
    registrar_traceback_rico: bool = True
    usar_cores: bool = True

    @classmethod
    def from_env(cls) -> "LoggerConfig":
        """Cria uma configuracao com base nas variaveis de ambiente.

        Variaveis reconhecidas:
        - LOG_LEVEL: ex. DEBUG, INFO, WARNING...
        - LOG_FILE: caminho do arquivo de log (anexa por padrao).
        - LOG_OVERWRITE: quando verdadeiro, recria o arquivo a cada execucao.
        - LOG_SHOW_TIME: define se o horario deve ser exibido (padrao True).
        - LOG_COLOR: habilita/desabilita cores no terminal (padrao True).
        - LOG_RICH_TRACEBACK: ativa stacktrace estilizada (padrao True).
        """

        cfg = cls()
        nivel = os.getenv("LOG_LEVEL")
        if nivel:
            cfg.nivel_minimo = nivel

        arquivo = os.getenv("LOG_FILE")
        if arquivo:
            cfg.arquivo_log = arquivo

        sobrescrever = _env_flag("LOG_OVERWRITE")
        if sobrescrever is not None:
            cfg.sobrescrever_arquivo = sobrescrever

        mostrar_tempo = _env_flag("LOG_SHOW_TIME")
        if mostrar_tempo is not None:
            cfg.mostrar_tempo = mostrar_tempo

        usar_cores = _env_flag("LOG_COLOR")
        if usar_cores is not None:
            cfg.usar_cores = usar_cores

        traceback_flag = _env_flag("LOG_RICH_TRACEBACK")
        if traceback_flag is not None:
            cfg.registrar_traceback_rico = traceback_flag

        return cfg


class FarmLogger:
    """Implementacao principal do logger com API em portugues."""

    def __init__(self) -> None:
        self._config = LoggerConfig()
        self._console = Console(theme=_DEFAULT_THEME, highlight=False)
        self._nivel_minimo = _resolver_nivel(self._config.nivel_minimo)
        self._arquivo_handle = None
        self._atexit_registrado = False
        self._contexto_padrao: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Configuracao e contexto
    # ------------------------------------------------------------------

    @property
    def config(self) -> LoggerConfig:
        """Retorna a configuracao ativa para fins de inspecao."""

        return self._config

    def configure(self, config: LoggerConfig) -> None:
        """Aplica uma nova configuracao ao logger."""

        global _TRACEBACK_INSTALADO

        self._config = config
        self._nivel_minimo = _resolver_nivel(config.nivel_minimo)

        if config.usar_cores:
            self._console = Console(theme=_DEFAULT_THEME, highlight=False)
        else:
            self._console = Console(highlight=False, no_color=True)

        if self._arquivo_handle:
            self._arquivo_handle.close()
            self._arquivo_handle = None
            self._atexit_registrado = False

        if config.registrar_traceback_rico and not _TRACEBACK_INSTALADO:
            install_rich_traceback(show_locals=False)
            _TRACEBACK_INSTALADO = True

    def atualizar_contexto_padrao(self, **dados: Any) -> None:
        """Adiciona ou atualiza campos que aparecem em todos os logs."""

        self._contexto_padrao.update(self._filtrar_dados(dados))

    def limpar_contexto_padrao(self, *chaves: str) -> None:
        """Remove campos do contexto padrao.

        Quando nenhuma chave e fornecida, o contexto padrao e limpo por
        completo.
        """

        if not chaves:
            self._contexto_padrao.clear()
            return
        for chave in chaves:
            self._contexto_padrao.pop(chave, None)

    def com_contexto(self, **dados: Any) -> "_ScopedLogger":
        """Retorna um logger derivado com contexto adicional.

        Ideal para anexar informacoes fixas (ex.: conta, etapa, id) sem
        repetir kwargs em todas as chamadas.
        """

        contexto = self._filtrar_dados(dados)
        return _ScopedLogger(self, contexto)

    # ------------------------------------------------------------------
    # API publica de logging
    # ------------------------------------------------------------------

    def debug(self, mensagem: str, **dados: Any) -> None:
        self._log("debug", mensagem, dados, None)

    def info(self, mensagem: str, **dados: Any) -> None:
        self._log("info", mensagem, dados, None)

    def sucesso(self, mensagem: str, **dados: Any) -> None:
        self._log("sucesso", mensagem, dados, None)

    def aviso(self, mensagem: str, **dados: Any) -> None:
        self._log("aviso", mensagem, dados, None)

    def erro(self, mensagem: str, **dados: Any) -> None:
        self._log("erro", mensagem, dados, None)

    def critico(self, mensagem: str, **dados: Any) -> None:
        self._log("critico", mensagem, dados, None)

    @contextmanager
    def etapa(
        self,
        titulo: str,
        mensagem_inicial: Optional[str] = None,
        mensagem_sucesso: Optional[str] = None,
        mensagem_falha: Optional[str] = None,
        **dados: Any,
    ):
        """Context manager que loga inicio/sucesso/falha de uma etapa."""

        dados_limpos = self._filtrar_dados(dados)
        with self._etapa_contexto(None, titulo, mensagem_inicial, mensagem_sucesso, mensagem_falha, dados_limpos):
            yield

    # ------------------------------------------------------------------
    # Implementacao interna
    # ------------------------------------------------------------------

    def _filtrar_dados(self, dados: Mapping[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in dados.items() if v is not None}

    def _deve_emitir(self, nivel: str) -> bool:
        return _resolver_nivel(nivel) >= self._nivel_minimo

    def _log(
        self,
        nivel: str,
        mensagem: str,
        dados: Mapping[str, Any],
        contexto_extra: Optional[Mapping[str, Any]],
    ) -> None:
        if not self._deve_emitir(nivel):
            return

        dados_limpos = self._filtrar_dados(dados)
        contexto = dict(self._contexto_padrao)
        if contexto_extra:
            contexto.update(self._filtrar_dados(contexto_extra))

        self._emitir_console(nivel, mensagem, contexto, dados_limpos)
        self._emitir_arquivo(nivel, mensagem, contexto, dados_limpos)

    def _emitir_console(
        self,
        nivel: str,
        mensagem: str,
        contexto: Mapping[str, Any],
        dados: Mapping[str, Any],
    ) -> None:
        texto = Text()
        if self._config.mostrar_tempo:
            texto.append(self._agora(), style="log.time")
            texto.append("  ")

        nivel_normalizado = _normalizar_nivel(nivel)
        estilo = f"log.{nivel_normalizado}"

        texto.append(f"[{nivel_normalizado.upper()}]", style=estilo)
        texto.append("  ")
        texto.append(mensagem, style=estilo)

        extras = self._formatar_extras(contexto, dados)
        if extras:
            texto.append("  ")
            texto.append(extras, style="log.contexto")

        self._console.print(texto)

    def _emitir_arquivo(
        self,
        nivel: str,
        mensagem: str,
        contexto: Mapping[str, Any],
        dados: Mapping[str, Any],
    ) -> None:
        if not self._config.arquivo_log:
            return

        linha = self._linha_arquivo(nivel, mensagem, contexto, dados)
        handle = self._obter_handle()
        handle.write(linha + "\n")
        handle.flush()

    def _obter_handle(self):
        if self._arquivo_handle is None:
            path = Path(self._config.arquivo_log)
            path.parent.mkdir(parents=True, exist_ok=True)
            modo = "w" if self._config.sobrescrever_arquivo else "a"
            self._arquivo_handle = path.open(modo, encoding="utf-8")
            if not self._atexit_registrado:
                atexit.register(self.close)
                self._atexit_registrado = True
        return self._arquivo_handle

    def _formatar_extras(
        self,
        contexto: Mapping[str, Any],
        dados: Mapping[str, Any],
    ) -> str:
        partes: list[str] = []
        if contexto:
            partes.extend(self._formatar_dict(contexto))
        if dados:
            partes.extend(self._formatar_dict(dados))
        return " ".join(partes)

    def _formatar_dict(self, valores: Mapping[str, Any]) -> Iterable[str]:
        for chave in sorted(valores):
            partes = f"{chave}={self._formatar_valor(valores[chave])}"
            yield partes

    def _formatar_valor(self, valor: Any) -> str:
        if isinstance(valor, (int, float)):
            return str(valor)
        if isinstance(valor, str):
            if valor.strip() == valor and " " not in valor:
                return valor
            return repr(valor)
        if valor is None:
            return "None"
        return repr(valor)

    def _linha_arquivo(
        self,
        nivel: str,
        mensagem: str,
        contexto: Mapping[str, Any],
        dados: Mapping[str, Any],
    ) -> str:
        partes = [self._agora(data=True), nivel.upper(), mensagem]
        if contexto:
            partes.append("contexto=" + ",".join(self._formatar_dict(contexto)))
        if dados:
            partes.append("dados=" + ",".join(self._formatar_dict(dados)))
        return " | ".join(partes)

    def _agora(self, data: bool = False) -> str:
        fmt = "%Y-%m-%d %H:%M:%S" if data else "%H:%M:%S"
        return datetime.now().strftime(fmt)

    def close(self) -> None:
        """Fecha o arquivo de log (quando houver)."""

        if self._arquivo_handle:
            self._arquivo_handle.close()
            self._arquivo_handle = None
            self._atexit_registrado = False

    def _etapa_contexto(
        self,
        contexto_extra: Optional[Mapping[str, Any]],
        titulo: str,
        mensagem_inicial: Optional[str],
        mensagem_sucesso: Optional[str],
        mensagem_falha: Optional[str],
        dados: Mapping[str, Any],
    ):
        @contextmanager
        def _ctx():
            inicio = mensagem_inicial or f"Iniciando etapa: {titulo}"
            sucesso = mensagem_sucesso or f"Etapa concluida: {titulo}"
            falha = mensagem_falha or f"Falha na etapa: {titulo}"

            self._log("info", inicio, dados, contexto_extra)
            try:
                yield
            except Exception:
                self._log("erro", falha, dados, contexto_extra)
                raise
            else:
                self._log("sucesso", sucesso, dados, contexto_extra)

        return _ctx()


class _ScopedLogger:
    """Wrapper leve para adicionar contexto fixo em um logger existente."""

    def __init__(self, base: FarmLogger, contexto: Mapping[str, Any]) -> None:
        self._base = base
        self._contexto = dict(contexto)

    def com_contexto(self, **dados: Any) -> "_ScopedLogger":
        novo = dict(self._contexto)
        novo.update(self._base._filtrar_dados(dados))
        return _ScopedLogger(self._base, novo)

    def debug(self, mensagem: str, **dados: Any) -> None:
        self._base._log("debug", mensagem, dados, self._contexto)

    def info(self, mensagem: str, **dados: Any) -> None:
        self._base._log("info", mensagem, dados, self._contexto)

    def sucesso(self, mensagem: str, **dados: Any) -> None:
        self._base._log("sucesso", mensagem, dados, self._contexto)

    def aviso(self, mensagem: str, **dados: Any) -> None:
        self._base._log("aviso", mensagem, dados, self._contexto)

    def erro(self, mensagem: str, **dados: Any) -> None:
        self._base._log("erro", mensagem, dados, self._contexto)

    def critico(self, mensagem: str, **dados: Any) -> None:
        self._base._log("critico", mensagem, dados, self._contexto)

    @contextmanager
    def etapa(
        self,
        titulo: str,
        mensagem_inicial: Optional[str] = None,
        mensagem_sucesso: Optional[str] = None,
        mensagem_falha: Optional[str] = None,
        **dados: Any,
    ):
        dados_limpos = self._base._filtrar_dados(dados)
        with self._base._etapa_contexto(
            self._contexto,
            titulo,
            mensagem_inicial,
            mensagem_sucesso,
            mensagem_falha,
            dados_limpos,
        ):
            yield


# Instancia global simples -------------------------------------------------

log = FarmLogger()


def configurar_logging(config: Optional[LoggerConfig] = None, **overrides: Any) -> FarmLogger:
    """Configura o logger global e o retorna para encadeamento.

    Quando nenhuma configuracao e informada, os valores sao lidos das
    variaveis de ambiente suportadas.
    """

    if config is None:
        config = LoggerConfig.from_env()
    if overrides:
        config = dataclasses.replace(config, **overrides)
    log.configure(config)
    return log


# Configuracao inicial baseada no ambiente -------------------------------

configurar_logging()

__all__ = ["LoggerConfig", "FarmLogger", "configurar_logging", "log"]
