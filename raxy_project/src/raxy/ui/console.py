"""
Wrapper centralizado para a interface de console (Rich).
"""

from rich.console import Console as RichConsole
from rich.theme import Theme

# Tema personalizado para o Raxy
raxy_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "highlight": "magenta",
})

# Singleton do Console
_console = RichConsole(theme=raxy_theme)


def get_console() -> RichConsole:
    """Retorna a instância global do console."""
    return _console


def print_info(message: str) -> None:
    _console.print(f"[info]ℹ[/info] {message}")


def print_success(message: str) -> None:
    _console.print(f"[success]✔[/success] {message}")


def print_warning(message: str) -> None:
    _console.print(f"[warning]⚠[/warning] {message}")


def print_error(message: str) -> None:
    _console.print(f"[error]✖ {message}[/error]")
