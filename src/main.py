"""Batch runner that reads accounts from users.txt and executes flows.

Formato do arquivo `users.txt` (uma conta por linha):
    email:senha
Linhas em branco ou iniciadas por `#` são ignoradas.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from resources import (
    login,
    goto_rewards_page,
    set_profile,
    build_user_agent_args,
)
from resources.accounts import load_users


def main() -> None:
    users_file = os.getenv("USERS_FILE", "users.txt")
    actions = os.getenv("ACTIONS", "login,rewards").split(",")
    actions = [a.strip().lower() for a in actions if a.strip()]

    accounts = load_users(users_file)
    if not accounts:
        print(f"Nenhuma conta válida encontrada em {users_file}")
        return

    print(f"Encontradas {len(accounts)} conta(s) em {users_file}")

    for acc in accounts:
        profile = acc.profile_id
        # Garante/atualiza UA e prepara args
        ua = set_profile(profile)
        add_args = build_user_agent_args(profile)

        print(f"\n==> Processando conta: {acc.email} (perfil: {profile})")
        # Evitar logar senha

        if "login" in actions:
            try:
                login(profile=profile, add_arguments=add_args, data={"email": acc.email, "password": acc.password})
            except Exception as e:
                print(f"[login] erro para {acc.email}: {e}")

        if "rewards" in actions:
            try:
                goto_rewards_page(profile=profile, add_arguments=add_args)
            except Exception as e:
                print(f"[rewards] erro para {acc.email}: {e}")


if __name__ == "__main__":
    main()
