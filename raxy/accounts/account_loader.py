"""Service responsible for loading accounts from the credential file."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .account import Account
from .profile_identifier import ProfileIdentifier


class AccountLoader:
    """Parse plain text files and yield :class:`Account` instances."""

    def __init__(self, source: str | Path) -> None:
        self._source = Path(source)

    def load(self) -> List[Account]:
        """Read the configured file and return valid accounts only."""

        if not self._source.exists():
            raise FileNotFoundError(f"Account file not found: {self._source}")

        accounts: List[Account] = []
        for raw_line in self._read_lines(self._source):
            email, password = self._split(raw_line)
            if not email or not password:
                continue
            profile_id = ProfileIdentifier.build(email)
            accounts.append(Account(email=email, password=password, profile_id=profile_id))
        return accounts

    def _read_lines(self, file_path: Path) -> Iterable[str]:
        """Yield relevant lines removing comments and blanks."""

        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                cleaned = line.strip()
                if not cleaned or cleaned.startswith("#"):
                    continue
                if ":" not in cleaned:
                    continue
                yield cleaned

    def _split(self, entry: str) -> tuple[str, str]:
        """Split a ``email:password`` entry into its components."""

        email, password = (part.strip() for part in entry.split(":", 1))
        return email, password


__all__ = ["AccountLoader"]
