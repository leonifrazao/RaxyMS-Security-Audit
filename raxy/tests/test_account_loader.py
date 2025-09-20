"""Tests for the account loading helpers."""

from __future__ import annotations

import pathlib
import tempfile
import unittest

from raxy.accounts.account_loader import AccountLoader


class AccountLoaderTests(unittest.TestCase):
    """Validate parsing behaviours of :class:`AccountLoader`."""

    def test_load_ignores_invalid_lines(self) -> None:
        """Lines without a password should not produce accounts."""

        content = """
        # comment
        valid@example.com:password
        invalid_line

        another@example.com : secret
        """
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as handle:
            handle.write(content)
            path = pathlib.Path(handle.name)

        try:
            loader = AccountLoader(path)
            accounts = loader.load()
        finally:
            path.unlink(missing_ok=True)

        emails = [account.email for account in accounts]
        self.assertEqual(emails, ["valid@example.com", "another@example.com"])

    def test_profile_identifiers_are_unique(self) -> None:
        """Sanitisation keeps identifiers stable and unique."""

        content = """
        user@example.com:one
        user@another.com:two
        user+alias@example.com:three
        """
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as handle:
            handle.write(content)
            path = pathlib.Path(handle.name)

        try:
            loader = AccountLoader(path)
            accounts = loader.load()
        finally:
            path.unlink(missing_ok=True)

        identifiers = [account.profile_id for account in accounts]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(all(identifier for identifier in identifiers))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
