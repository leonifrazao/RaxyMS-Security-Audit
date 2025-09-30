"""Client example consuming a FastPIPE daemon service."""
from __future__ import annotations

# Importa o serviço para garantir que ele está rodando em background.
import daemon_service  # noqa: F401
import fastpipe as fp


if __name__ == "__main__":
    client = fp.connect("demo-service", argumento="Olá, FastPIPE!")
    print(client.home())
    print(client.get())
    print(client.soma(10, 20))
