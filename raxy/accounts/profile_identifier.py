"""Utilities for generating deterministic profile identifiers."""

from __future__ import annotations

import hashlib
import re


class ProfileIdentifier:
    """Create sanitized profile identifiers derived from an email address."""

    _SAFE_PATTERN = re.compile(r"[^a-z0-9._-]+")
    _HASH_SIZE = 6
    _MAX_LENGTH = 80

    @classmethod
    def build(cls, email: str) -> str:
        """Return a stable identifier even when the e-mail is malformed."""

        normalized = email.strip().lower()
        if not normalized:
            return "profile"

        replaced = normalized.replace("@", "_at_")
        safe_fragment = cls._SAFE_PATTERN.sub("_", replaced).strip("_") or "profile"
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[: cls._HASH_SIZE]
        limit = max(1, cls._MAX_LENGTH - len(digest) - 1)
        prefix = safe_fragment[:limit]
        return f"{prefix}_{digest}" if prefix else digest


__all__ = ["ProfileIdentifier"]
