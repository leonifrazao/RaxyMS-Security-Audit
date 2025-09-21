"""Entrada da linha de comando para o Raxy."""

from __future__ import annotations

from core.accounts import carregar_contas
from core.profiles import GerenciadorPerfil
from core.rewards import Rewards
from core.logging import log

def main():
    # Carrega contas
    contas = carregar_contas("users.txt")
    
    # Inicializa sistema
    rewards = Rewards()
    
    for conta in contas:
        try:
            GerenciadorPerfil(conta.email).agente_usuario()
            log.info(f"Processando conta: {conta.email}")
            
            # Faz login
            sessao = rewards.login(
                profile=conta.email,
                data={"email": conta.email, "password": conta.senha}
            )
            # Obtém pontos
            pontos_info = rewards.obter_pontos(base=sessao, bypass_request_token=True)
            log.sucesso(f"Pontos disponíveis: {pontos_info}")
            
            # Obtém recompensas  
            recompensas = rewards.obter_recompensas(base=sessao)
            daily_sets = recompensas.get("daily_sets", [])
            log.sucesso(f"Recompensas obtidas", quantidade=len(daily_sets))
            
        except Exception as e:
            print(f"Erro ao processar {conta.email}: {e}")
            continue

if __name__ == "__main__":
    main()
