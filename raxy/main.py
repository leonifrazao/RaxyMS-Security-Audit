"""Entrada da linha de comando para o Raxy."""

from __future__ import annotations

import pathlib
import sys

if __package__ in {None, ""}:
    ROOT = pathlib.Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from raxy.services.executor import executar_cli  # type: ignore[assignment]
else:
    from .services.executor import executar_cli


def main() -> None:
    executar_cli()


if __name__ == "__main__":
    main()
