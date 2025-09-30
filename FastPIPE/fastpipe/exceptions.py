"""Custom exceptions for the FastPIPE library."""

from __future__ import annotations


class FastPipeError(Exception):
    """Base exception for FastPIPE-related errors."""


class ServiceAlreadyExists(FastPipeError):
    """Raised when attempting to create a service that already exists and is active."""


class ServiceNotFound(FastPipeError):
    """Raised when a requested service cannot be found in the registry."""


class RemoteExecutionError(FastPipeError):
    """Raised when a remote call fails inside the service."""
