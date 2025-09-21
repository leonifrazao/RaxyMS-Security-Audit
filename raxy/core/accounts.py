import re
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Conta:
    email: str
    senha: str
    id_perfil: str

def carregar_contas(caminho_arquivo):
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    contas = []
    with caminho.open("r", encoding="utf-8") as handle:
        for linha in handle:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue

            if ":" not in linha:
                continue
                
            email, senha = linha.split(":", 1)
            email, senha = email.strip(), senha.strip()
            
            if not email or not senha:
                continue

            # ID do perfil baseado no email
            base = email.lower().replace("@", "_at_")
            id_perfil = re.sub(r"[^a-z0-9._-]+", "_", base).strip("_") or "perfil"
            
            contas.append(Conta(email=email, senha=senha, id_perfil=id_perfil))

    return contas