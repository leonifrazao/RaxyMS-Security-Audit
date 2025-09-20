"""Domain representation for user accounts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Account:
    """Immutable credential holder used throughout the application."""

    email: str
    password: str
    profile_id: str

    def masked_email(self) -> str:
        """Return a redacted version of the email for log messages."""

        if "@" not in self.email:
            return self.email
        name, domain = self.email.split("@", 1)
        if len(name) <= 2:
            return f"***@{domain}"
        return f"{name[0]}***{name[-1]}@{domain}"


__all__ = ["Account"]
