"""Entrada da linha de comando para o Raxy."""

from __future__ import annotations

from container import create_injector
from interfaces.services import IExecutorEmLoteService


def main() -> None:
    injector = create_injector()
    executor = injector.get(IExecutorEmLoteService)
    executor.executar()


if __name__ == "__main__":
    main()
