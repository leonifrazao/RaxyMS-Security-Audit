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

from .helpers import get_env_bool

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
    """Normaliza o nome de nível fornecido para variantes suportadas."""

    chave = nome.lower()
    return _NORMALIZED_NAMES.get(chave, "info")


def _resolver_nivel(valor: str | int) -> int:
    """Converte uma representação de nível (string/int) em valor numérico."""

    if isinstance(valor, int):
        return valor
    chave = valor.lower()
    return _LEVEL_MAP.get(chave, _LEVEL_MAP["info"])

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

        sobrescrever = get_env_bool("LOG_OVERWRITE")
        if sobrescrever is not None:
            cfg.sobrescrever_arquivo = sobrescrever

        mostrar_tempo = get_env_bool("LOG_SHOW_TIME")
        if mostrar_tempo is not None:
            cfg.mostrar_tempo = mostrar_tempo

        usar_cores = get_env_bool("LOG_COLOR")
        if usar_cores is not None:
            cfg.usar_cores = usar_cores

        traceback_flag = get_env_bool("LOG_RICH_TRACEBACK")
        if traceback_flag is not None:
            cfg.registrar_traceback_rico = traceback_flag

        return cfg


class FarmLogger:
    """Implementacao principal do logger com API em portugues."""

    def __init__(self) -> None:
        """Instancia o logger com configuração padrão baseada em ambiente."""

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
        """Aplica uma nova configuração ao logger.

        Args:
            config: Instância pronta de :class:`LoggerConfig`.
        """

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
        """Adiciona ou atualiza campos que aparecem em todos os logs.

        Args:
            **dados: Chave/valor a ser adicionado ao contexto padrão.
        """

        self._contexto_padrao.update(self._filtrar_dados(dados))

    def limpar_contexto_padrao(self, *chaves: str) -> None:
        """Remove campos do contexto padrão.

        Quando nenhuma chave e fornecida, o contexto padrao e limpo por
        completo.
        
        Args:
            *chaves: Campos a remover. Quando vazio, zera o contexto.
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

        Args:
            **dados: Parâmetros adicionais incorporados em todas as mensagens.

        Returns:
            Instância de :class:`_ScopedLogger` com o contexto agregado.
        """

        contexto = self._filtrar_dados(dados)
        return _ScopedLogger(self, contexto)

    # ------------------------------------------------------------------
    # API publica de logging
    # ------------------------------------------------------------------

    def debug(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível DEBUG."""
        self._log("debug", mensagem, dados, None)

    def info(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível INFO."""
        self._log("info", mensagem, dados, None)

    def sucesso(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível SUCESSO (25)."""
        self._log("sucesso", mensagem, dados, None)

    def aviso(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível AVISO."""
        self._log("aviso", mensagem, dados, None)

    def erro(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível ERRO."""
        self._log("erro", mensagem, dados, None)

    def critico(self, mensagem: str, **dados: Any) -> None:
        """Emite log nível CRÍTICO."""
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
        """Context manager que registra início, sucesso e falha de uma etapa.

        Args:
            titulo: Nome da etapa exibido nos logs.
            mensagem_inicial: Mensagem opcional emitida ao entrar no contexto.
            mensagem_sucesso: Mensagem emitida quando o bloco termina sem erros.
            mensagem_falha: Mensagem emitida quando ocorre exceção.
            **dados: Metadados adicionais incluídos em cada log gerado.
        """

        dados_limpos = self._filtrar_dados(dados)
        with self._etapa_contexto(None, titulo, mensagem_inicial, mensagem_sucesso, mensagem_falha, dados_limpos):
            yield

    # ------------------------------------------------------------------
    # Implementacao interna
    # ------------------------------------------------------------------

    def _filtrar_dados(self, dados: Mapping[str, Any]) -> Dict[str, Any]:
        """Remove pares com valores ``None`` preservando o restante."""

        return {k: v for k, v in dados.items() if v is not None}

    def _deve_emitir(self, nivel: str) -> bool:
        """Retorna ``True`` quando o nível atual deve ser emitido."""

        return _resolver_nivel(nivel) >= self._nivel_minimo

    def _log(
        self,
        nivel: str,
        mensagem: str,
        dados: Mapping[str, Any],
        contexto_extra: Optional[Mapping[str, Any]],
    ) -> None:
        """Dispara o fluxo de logging consolidando contexto e destino."""

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
        """Emite a mensagem formatada no console Rich."""

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
        """Persiste a mensagem no arquivo de log quando configurado."""

        if not self._config.arquivo_log:
            return

        linha = self._linha_arquivo(nivel, mensagem, contexto, dados)
        handle = self._obter_handle()
        handle.write(linha + "\n")
        handle.flush()

    def _obter_handle(self):
        """Abre (se necessário) o handle do arquivo de log."""

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
        """Formata pares chave=valor para anexar às mensagens."""

        partes: list[str] = []
        if contexto:
            partes.extend(self._formatar_dict(contexto))
        if dados:
            partes.extend(self._formatar_dict(dados))
        return " ".join(partes)

    def _formatar_dict(self, valores: Mapping[str, Any]) -> Iterable[str]:
        """Itera sobre o dicionário gerando ``chave=valor`` ordenados."""

        for chave in sorted(valores):
            partes = f"{chave}={self._formatar_valor(valores[chave])}"
            yield partes

    def _formatar_valor(self, valor: Any) -> str:
        """Formata valores em representação amigável para logs de contexto."""

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
        """Monta a linha padrão escrita no arquivo de log."""

        partes = [self._agora(data=True), nivel.upper(), mensagem]
        if contexto:
            partes.append("contexto=" + ",".join(self._formatar_dict(contexto)))
        if dados:
            partes.append("dados=" + ",".join(self._formatar_dict(dados)))
        return " | ".join(partes)

    def _agora(self, data: bool = False) -> str:
        """Retorna o timestamp atual em formato string."""

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
        """Cria o context manager interno usado por ``etapa``."""

        @contextmanager
        def _ctx():
            """Contexto que loga início, falha e sucesso de etapas."""

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
        """Inicializa o escopo preservando o contexto fixo fornecido."""

        self._base = base
        self._contexto = dict(contexto)

    def com_contexto(self, **dados: Any) -> "_ScopedLogger":
        """Retorna novo escopo de logger acumulando mais contexto."""

        novo = dict(self._contexto)
        novo.update(self._base._filtrar_dados(dados))
        return _ScopedLogger(self._base, novo)

    def debug(self, mensagem: str, **dados: Any) -> None:
        """Emite log DEBUG reaproveitando o contexto escopo."""

        self._base._log("debug", mensagem, dados, self._contexto)

    def info(self, mensagem: str, **dados: Any) -> None:
        """Emite log INFO reaproveitando o contexto escopo."""

        self._base._log("info", mensagem, dados, self._contexto)

    def sucesso(self, mensagem: str, **dados: Any) -> None:
        """Emite log SUCESSO reaproveitando o contexto escopo."""

        self._base._log("sucesso", mensagem, dados, self._contexto)

    def aviso(self, mensagem: str, **dados: Any) -> None:
        """Emite log AVISO reaproveitando o contexto escopo."""

        self._base._log("aviso", mensagem, dados, self._contexto)

    def erro(self, mensagem: str, **dados: Any) -> None:
        """Emite log ERRO reaproveitando o contexto escopo."""

        self._base._log("erro", mensagem, dados, self._contexto)

    def critico(self, mensagem: str, **dados: Any) -> None:
        """Emite log CRÍTICO reaproveitando o contexto escopo."""

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
        """Context manager equivalente ao do logger base, herdando contexto."""

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
