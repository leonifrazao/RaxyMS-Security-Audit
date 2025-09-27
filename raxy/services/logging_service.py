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
import threading

from rich.console import Console
from rich.theme import Theme
from rich.text import Text
from rich.traceback import install as install_rich_traceback

from interfaces.services import ILoggingService

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

        return cfg


class FarmLogger(ILoggingService):
    """Implementacao principal do logger com API em portugues."""

    def __init__(self) -> None:
        """Instancia o logger com configuração padrão baseada em ambiente."""

        self._config = LoggerConfig()
        self._console = Console(theme=_DEFAULT_THEME, highlight=False)
        valor_nivel = self._config.nivel_minimo
        if isinstance(valor_nivel, int):
            self._nivel_minimo = valor_nivel
        else:
            chave = str(valor_nivel).lower()
            self._nivel_minimo = _LEVEL_MAP.get(chave, _LEVEL_MAP["info"])
        self._arquivo_handle = None
        self._atexit_registrado = False
        self._contexto_padrao: Dict[str, Any] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Configuracao e contexto
    # ------------------------------------------------------------------

    @property
    def config(self) -> LoggerConfig:
        """Retorna a configuracao ativa para fins de inspecao."""

        return self._config

    def configure(self, config: LoggerConfig) -> None:
        """Aplica uma nova configuração ao logger.

        Args:
            config: Instância pronta de :class:`LoggerConfig`.
        """

        global _TRACEBACK_INSTALADO

        with self._lock:
            self._config = config
            valor_nivel = config.nivel_minimo
            if isinstance(valor_nivel, int):
                self._nivel_minimo = valor_nivel
            else:
                chave = str(valor_nivel).lower()
                self._nivel_minimo = _LEVEL_MAP.get(chave, _LEVEL_MAP["info"])

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
        """Adiciona ou atualiza campos que aparecem em todos os logs.

        Args:
            **dados: Chave/valor a ser adicionado ao contexto padrão.
        """
        with self._lock:
            filtrados = {k: v for k, v in dados.items() if v is not None}
            self._contexto_padrao.update(filtrados)

    def limpar_contexto_padrao(self, *chaves: str) -> None:
        """Remove campos do contexto padrão.

        Quando nenhuma chave e fornecida, o contexto padrao e limpo por
        completo.

        Args:
            *chaves: Campos a remover. Quando vazio, zera o contexto.
        """
        with self._lock:
            if not chaves:
                self._contexto_padrao.clear()
                return
            for chave in chaves:
                self._contexto_padrao.pop(chave, None)

    def com_contexto(self, **dados: Any) -> "ScopedLogger":
        """Retorna um logger derivado com contexto adicional.

        Ideal para anexar informacoes fixas (ex.: conta, etapa, id) sem
        repetir kwargs em todas as chamadas.

        Args:
            **dados: Parâmetros adicionais incorporados em todas as mensagens.

        Returns:
            Instância de :class:`ScopedLogger` com o contexto agregado.
        """

        contexto = {k: v for k, v in dados.items() if v is not None}
        return ScopedLogger(self, contexto)

    # ------------------------------------------------------------------
    # API publica de logging
    # ------------------------------------------------------------------

    def debug(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível DEBUG."""
        self.registrar_evento("debug", mensagem, dados, None)

    def info(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível INFO."""
        self.registrar_evento("info", mensagem, dados, None)

    def sucesso(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível SUCESSO (25)."""
        self.registrar_evento("sucesso", mensagem, dados, None)

    def aviso(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível AVISO."""
        self.registrar_evento("aviso", mensagem, dados, None)

    def erro(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível ERRO."""
        self.registrar_evento("erro", mensagem, dados, None)

    def critico(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível CRÍTICO."""
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
        """Context manager que registra início, sucesso e falha de uma etapa.

        Args:
            titulo: Nome da etapa exibido nos logs.
            mensagem_inicial: Mensagem opcional emitida ao entrar no contexto.
            mensagem_sucesso: Mensagem emitida quando o bloco termina sem erros.
            mensagem_falha: Mensagem emitida quando ocorre exceção.
            **dados: Metadados adicionais incluídos em cada log gerado.
        """

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
    # Implementacao interna
    # ------------------------------------------------------------------

    def deve_emitir(self, nivel: str | int) -> bool:
        """Indica se o nível solicitado deve ser emitido."""

        if isinstance(nivel, int):
            valor = nivel
        else:
            chave = str(nivel).lower()
            valor = _LEVEL_MAP.get(chave, _LEVEL_MAP["info"])
        return valor >= self._nivel_minimo

    def registrar_evento(
        self,
        nivel: str | int,
        mensagem: str,
        dados: Mapping[str, Any],
        contexto_extra: Optional[Mapping[str, Any]],
    ) -> None:
        """Consolida dados, contexto e emissões em console/arquivo."""

        if not self.deve_emitir(nivel):
            return

        dados_limpos = {k: v for k, v in (dados or {}).items() if v is not None}

        if isinstance(nivel, int):
            valor_nivel = nivel
            chave_referencia = next(
                (nome for nome, valor in _LEVEL_MAP.items() if valor == valor_nivel),
                "info",
            )
        else:
            chave_normalizada = str(nivel).lower()
            valor_nivel = _LEVEL_MAP.get(chave_normalizada, _LEVEL_MAP["info"])
            chave_referencia = _NORMALIZED_NAMES.get(chave_normalizada, "info")

        instante = datetime.now()

        with self._lock:
            contexto = dict(self._contexto_padrao)
            if contexto_extra:
                for chave, valor in contexto_extra.items():
                    if valor is not None:
                        contexto[chave] = valor

            extras_partes = []
            if contexto:
                extras_partes.extend(self.formatar_dict(contexto))
            if dados_limpos:
                extras_partes.extend(self.formatar_dict(dados_limpos))
            extras_texto = " ".join(extras_partes)

            texto = Text()
            if self._config.mostrar_tempo:
                texto.append(instante.strftime("%H:%M:%S"), style="log.time")
                texto.append("  ")

            estilo = f"log.{chave_referencia}"
            texto.append(f"[{chave_referencia.upper()}]", style=estilo)
            texto.append("  ")
            texto.append(mensagem, style=estilo)

            if extras_texto:
                texto.append("  ")
                texto.append(extras_texto, style="log.contexto")

            self._console.print(texto)

            if self._config.arquivo_log:
                if self._arquivo_handle is None:
                    path = Path(self._config.arquivo_log)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    modo = "w" if self._config.sobrescrever_arquivo else "a"
                    self._arquivo_handle = path.open(modo, encoding="utf-8")
                    if not self._atexit_registrado:
                        atexit.register(self.close)
                        self._atexit_registrado = True

                partes_arquivo = [instante.strftime("%Y-%m-%d %H:%M:%S"), chave_referencia.upper(), mensagem]
                if contexto:
                    partes_arquivo.append("contexto=" + ",".join(self.formatar_dict(contexto)))
                if dados_limpos:
                    partes_arquivo.append("dados=" + ",".join(self.formatar_dict(dados_limpos)))
                linha = " | ".join(partes_arquivo)
                self._arquivo_handle.write(linha + "\n")
                self._arquivo_handle.flush()

    def close(self) -> None:
        """Fecha o arquivo de log (quando houver)."""

        with self._lock:
            if self._arquivo_handle is not None:
                self._arquivo_handle.close()
                self._arquivo_handle = None
                self._atexit_registrado = False

    @staticmethod
    def formatar_valor(valor: Any) -> str:
        """Transforma valores em representação amigável para logs."""

        if isinstance(valor, (int, float)):
            return str(valor)
        if isinstance(valor, str):
            if valor.strip() == valor and " " not in valor:
                return valor
            return repr(valor)
        if valor is None:
            return "None"
        return repr(valor)

    @classmethod
    def formatar_dict(cls, valores: Mapping[str, Any]) -> list[str]:
        """Converte dicionários em pares ``chave=valor`` ordenados."""

        return [f"{chave}={cls.formatar_valor(valores[chave])}" for chave in sorted(valores)]


class ScopedLogger(ILoggingService):
    """Wrapper leve para adicionar contexto fixo em um logger existente."""

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


# Instancia global simples -------------------------------------------------

log = FarmLogger()


def configurar_logging(config: Optional[LoggerConfig] = None, **overrides: Any) -> FarmLogger:
    """Configura o logger global e o retorna para encadeamento.

    Quando nenhuma configuracao e informada, os valores sao lidos das
    variaveis de ambiente suportadas.

    Args:
        config: Configuração opcional a ser aplicada.
        **overrides: Campos para sobrescrever na configuração final.

    Returns:
        Instância ``FarmLogger`` configurada.
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
