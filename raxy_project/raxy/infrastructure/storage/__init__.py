"""Implementações concretas de sistemas de armazenamento."""

from .local_filesystem import LocalFileSystem
from .mock_filesystem import MockFileSystem

__all__ = ["LocalFileSystem", "MockFileSystem"]
