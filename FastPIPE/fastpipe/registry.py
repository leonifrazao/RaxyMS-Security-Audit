"""Filesystem-backed service registry for FastPIPE."""
from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from .exceptions import ServiceAlreadyExists, ServiceNotFound


def _default_root() -> Path:
    env = os.environ.get("FASTPIPE_HOME")
    if env:
        return Path(env)
    return Path.cwd() / ".fastpipe"


_REGISTRY_ROOT = _default_root()
_SERVICES_DIR = _REGISTRY_ROOT / "services"
_REGISTRY_DIR = _REGISTRY_ROOT / "registry"


@dataclass
class ServiceRecord:
    """Metadata stored for each registered service."""

    name: str
    root: str  # filesystem path to the service workspace
    pid: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceRecord":
        return cls(name=data["name"], root=data["root"], pid=int(data["pid"]))

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "root": self.root, "pid": self.pid}

    @classmethod
    def load(cls, path: Path) -> "ServiceRecord":
        with path.open("r", encoding="utf-8") as fp:
            return cls.from_dict(json.load(fp))

    def dump(self, path: Path) -> None:
        temp_path = path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as fp:
            json.dump(self.to_dict(), fp)
        os.replace(temp_path, path)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def ensure_directories() -> None:
    _SERVICES_DIR.mkdir(parents=True, exist_ok=True)
    _REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def service_root(name: str) -> Path:
    ensure_directories()
    root = _SERVICES_DIR / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def _is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def register_service(record: ServiceRecord) -> None:
    ensure_directories()
    path = _REGISTRY_DIR / f"{record.name}.json"
    if path.exists():
        try:
            existing = ServiceRecord.load(path)
        except (json.JSONDecodeError, KeyError, ValueError):
            existing = None
        if existing and existing.pid != record.pid and _is_process_alive(existing.pid):
            raise ServiceAlreadyExists(
                f"Service '{record.name}' is already registered by pid {existing.pid}."
            )
    record.dump(path)


def unregister_service(name: str, *, expected_pid: int | None = None) -> None:
    path = _REGISTRY_DIR / f"{name}.json"
    if not path.exists():
        return
    if expected_pid is not None:
        try:
            existing = ServiceRecord.load(path)
        except (json.JSONDecodeError, KeyError, ValueError):
            existing = None
        if existing and existing.pid != expected_pid:
            return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def resolve_service(name: str) -> ServiceRecord:
    path = _REGISTRY_DIR / f"{name}.json"
    if not path.exists():
        raise ServiceNotFound(f"Service '{name}' was not found. Did you call fastpipe.create()?")
    try:
        record = ServiceRecord.load(path)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise ServiceNotFound(
            f"Service '{name}' has an invalid registry entry; try recreating the service."
        ) from exc
    if not _is_process_alive(record.pid):
        unregister_service(name)
        raise ServiceNotFound(
            f"Service '{name}' appears to be stale (process {record.pid} is not running)."
        )
    return record
