"""Account file loader for batch operations.

Parses a simple users file where each non-empty, non-comment line is:

    email:password

Whitespace around tokens is trimmed. Lines starting with `#` are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List


@dataclass(frozen=True)
class Account:
    email: str
    password: str
    profile_id: str


def _derive_profile_id(email: str) -> str:
    # Use local-part of email as profile id (safe and readable)
    local = email.split("@", 1)[0]
    return local or email.replace("@", "_")


def load_users(file_path: str | Path) -> List[Account]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    accounts: List[Account] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            # Skip invalid lines but continue processing others
            continue
        email, password = [p.strip() for p in line.split(":", 1)]
        if not email or not password:
            continue
        accounts.append(Account(email=email, password=password, profile_id=_derive_profile_id(email)))

    return accounts

