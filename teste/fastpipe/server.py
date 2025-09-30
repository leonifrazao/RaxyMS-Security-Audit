"""Server-side implementation for FastPIPE services using filesystem messaging."""
from __future__ import annotations

import asyncio
import atexit
import json
import multiprocessing
import os
import threading
import time
import uuid
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Optional, Tuple

from .exceptions import FastPipeError, ServiceNotFound
from .registry import (
    ServiceRecord,
    register_service,
    resolve_service,
    service_root,
    unregister_service,
)


JsonDict = Dict[str, Any]
EndpointSpec = Tuple[str, Callable[..., Any]]
CallableFactory = Callable[[List[Any], Dict[str, Any]], Callable[..., Any]]
_REQUEST_DIR = "requests"
_RESPONSE_DIR = "responses"

_ACTIVE_DAEMONS: List["DaemonHandle"] = []
_DAEMON_CLEANUP_REGISTERED = False


def _register_daemon_handle(handle: "DaemonHandle") -> None:
    global _DAEMON_CLEANUP_REGISTERED
    _ACTIVE_DAEMONS.append(handle)
    if not _DAEMON_CLEANUP_REGISTERED:
        atexit.register(_shutdown_daemons)
        _DAEMON_CLEANUP_REGISTERED = True


def _unregister_daemon_handle(handle: "DaemonHandle") -> None:
    try:
        _ACTIVE_DAEMONS.remove(handle)
    except ValueError:
        pass


def _shutdown_daemons() -> None:
    for handle in list(_ACTIVE_DAEMONS):
        try:
            handle.stop(timeout=0.5)
        except Exception:  # pragma: no cover - best-effort shutdown
            pass


class _FunctionFactory:
    def __init__(self, func: Callable[..., Any]) -> None:
        self._func = func

    def __call__(self, _ctor_args: List[Any], _ctor_kwargs: Dict[str, Any]) -> Callable[..., Any]:
        return self._func


class _InstanceMethodFactory:
    def __init__(self, cls: type, attr_name: str) -> None:
        self._cls = cls
        self._attr_name = attr_name

    def __call__(self, ctor_args: List[Any], ctor_kwargs: Dict[str, Any]) -> Callable[..., Any]:
        instance = self._cls(*ctor_args, **ctor_kwargs)
        return getattr(instance, self._attr_name)


class _StaticLikeFactory:
    def __init__(self, owner: type, attr_name: str) -> None:
        self._owner = owner
        self._attr_name = attr_name

    def __call__(self, _ctor_args: List[Any], _ctor_kwargs: Dict[str, Any]) -> Callable[..., Any]:
        return getattr(self._owner, self._attr_name)

class RegisteredFunction:
    """Internal wrapper that knows how to produce a callable target."""

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        factory: CallableFactory | None = None,
    ) -> None:
        self.name = name
        self.func = func
        self._factory = factory or (lambda *_: func)

    def invoke(
        self,
        args: List[Any],
        kwargs: Dict[str, Any],
        ctor_args: List[Any],
        ctor_kwargs: Dict[str, Any],
    ) -> Any:
        target = self._factory(ctor_args, ctor_kwargs)
        result = target(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result


class ServiceServer:
    """Maintains a registry of functions and responds to filesystem requests."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._registry: Dict[str, RegisteredFunction] = {}
        self._lock = threading.Lock()
        self._root = service_root(name)
        self._requests = self._root / _REQUEST_DIR
        self._responses = self._root / _RESPONSE_DIR
        self._requests.mkdir(parents=True, exist_ok=True)
        self._responses.mkdir(parents=True, exist_ok=True)
        self._server_thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._record: Optional[ServiceRecord] = None
        self._frozen = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def endpoints(self) -> MappingProxyType:
        with self._lock:
            return MappingProxyType({name: entry.func for name, entry in self._registry.items()})

    @property
    def root(self) -> Path:
        return self._root

    def _resolve_factory(self, func: Callable[..., Any], name: str) -> CallableFactory:
        owner = getattr(func, "__fastpipe_owner__", None)
        attr_name = getattr(func, "__fastpipe_attr__", name)
        descriptor = getattr(func, "__fastpipe_descriptor__", "instance")
        if owner is None:
            return _FunctionFactory(func)
        if descriptor in {"staticmethod", "classmethod"}:
            return _StaticLikeFactory(owner, attr_name)
        return _InstanceMethodFactory(owner, attr_name)

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        *,
        factory: CallableFactory | None = None,
    ) -> None:
        with self._lock:
            if self._frozen:
                raise FastPipeError("Service is running as a daemon; no new endpoints can be registered")
            if name in self._registry:
                raise FastPipeError(f"Endpoint '{name}' is already registered")
            resolved_factory = factory or self._resolve_factory(func, name)
            self._registry[name] = RegisteredFunction(name, func, resolved_factory)

    def start(self, *, daemon_thread: bool = True) -> None:
        if self._server_thread and self._server_thread.is_alive():
            return
        self._running.set()
        self._server_thread = threading.Thread(
            target=self._serve_loop,
            name=f"FastPIPE[{self._name}]",
            daemon=daemon_thread,
        )
        self._server_thread.start()

    def stop(self) -> None:
        self._running.clear()
        thread = self._server_thread
        if thread and thread.is_alive():
            thread.join(timeout=1)
        self._server_thread = None
        if self._record is not None:
            unregister_service(self._name, expected_pid=self._record.pid)
            self._record = None

    def set_frozen(self, value: bool) -> None:
        with self._lock:
            self._frozen = value

    def publish(self) -> ServiceRecord:
        if self._record is not None:
            return self._record
        record = ServiceRecord(name=self._name, root=str(self._root), pid=os.getpid())
        register_service(record)
        atexit.register(lambda: unregister_service(record.name, expected_pid=record.pid))
        self._record = record
        return record

    def run_forever(self, *, poll_interval: float = 0.5) -> None:
        """Block the current thread while the service keeps handling requests."""

        self.start()
        self.publish()
        try:
            while True:
                if not self._running.is_set():
                    break
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def snapshot_registry(self) -> List[EndpointSpec]:
        with self._lock:
            return [(name, entry.func) for name, entry in self._registry.items()]

    def _serve_loop(self) -> None:
        while self._running.is_set():
            handled = False
            for request_path in sorted(self._requests.glob("*.json")):
                handled = True
                try:
                    self._process_request(request_path)
                except Exception:
                    try:
                        request_path.unlink()
                    except FileNotFoundError:
                        pass
            if not handled:
                time.sleep(0.01)

    def _process_request(self, request_path: Path) -> None:
        try:
            raw = request_path.read_text(encoding="utf-8")
        finally:
            try:
                request_path.unlink()
            except FileNotFoundError:
                pass
        try:
            request = json.loads(raw)
        except json.JSONDecodeError:
            return
        response = self.handle_request(request)
        response_path = self._responses / f"{request.get('id', uuid.uuid4().hex)}.json"
        tmp = response_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(response), encoding="utf-8")
        os.replace(tmp, response_path)

    def handle_request(self, request: JsonDict) -> JsonDict:
        command = request.get("type")
        if command == "list_endpoints":
            with self._lock:
                return {"status": "ok", "result": sorted(self._registry.keys())}
        if command != "call":
            return {
                "status": "error",
                "error": {"type": "ProtocolError", "message": "Unknown command"},
            }
        endpoint = str(request.get("endpoint"))
        args = list(request.get("args", []))
        kwargs = dict(request.get("kwargs", {}))
        ctor_args = list(request.get("ctor_args", []))
        ctor_kwargs = dict(request.get("ctor_kwargs", {}))
        with self._lock:
            callable_entry = self._registry.get(endpoint)
        if callable_entry is None:
            return {
                "status": "error",
                "error": {"type": "NotFound", "message": f"Endpoint '{endpoint}' not found"},
            }
        try:
            result = callable_entry.invoke(args, kwargs, ctor_args, ctor_kwargs)
            json.dumps(result)
        except TypeError as exc:
            return {
                "status": "error",
                "error": {"type": "TypeError", "message": str(exc)},
            }
        except Exception as exc:  # pylint: disable=broad-except
            return {
                "status": "error",
                "error": {"type": exc.__class__.__name__, "message": str(exc)},
            }
        return {"status": "ok", "result": result}


class ServiceBuilder:
    """Public API exposed to user-land to register functions."""

    def __init__(self, server: ServiceServer, *, bootstrap: bool = True):
        self._server = server
        if bootstrap:
            self._server.start()
            self._server.publish()

    def register(
        self,
        explicit_name: str | None = None,
        *,
        alias: str | None = None,
        factory: CallableFactory | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            endpoint_name = explicit_name or func.__name__
            self._server.register(endpoint_name, func, factory=factory)
            if alias and alias != endpoint_name:
                self._server.register(alias, func, factory=factory)
            return func

        return decorator

    def _register_endpoint(
        self,
        name: str,
        func: Callable[..., Any],
        *,
        factory: CallableFactory | None = None,
    ) -> None:
        self._server.register(name, func, factory=factory)

    def routes(self) -> Dict[str, Callable[..., Any]]:
        return dict(self._server.endpoints)

    def daemon(self) -> "DaemonServiceBuilder":
        self._server.stop()
        return DaemonServiceBuilder(self._server, bootstrap=False)


class DaemonHandle:
    """Represents a background FastPIPE daemon process."""

    def __init__(
        self,
        service_name: str,
        process: multiprocessing.Process,
        cleanup: Callable[["DaemonHandle"], None] | None = None,
    ) -> None:
        self._service_name = service_name
        self._process = process
        self._cleanup = cleanup
        self._stopped = False

    @property
    def pid(self) -> Optional[int]:
        return self._process.pid

    @property
    def service(self) -> str:
        return self._service_name

    def is_running(self) -> bool:
        return self._process.is_alive() and not self._stopped

    def stop(self, *, timeout: float = 1.0) -> None:
        if self._stopped:
            return
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=timeout)
        else:
            self._process.join(timeout=timeout)
        unregister_service(self._service_name, expected_pid=self.pid)
        self._stopped = True
        if self._cleanup is not None:
            self._cleanup(self)
            self._cleanup = None

    def join(self, timeout: Optional[float] = None) -> None:
        self._process.join(timeout)


class DaemonServiceBuilder(ServiceBuilder):
    """Builder variant that exposes convenience helpers for daemon services."""

    def __init__(self, server: ServiceServer, *, bootstrap: bool = True):
        super().__init__(server, bootstrap=bootstrap)
        self._handle: Optional[DaemonHandle] = None

    def run(
        self,
        *,
        poll_interval: float = 0.5,
        wait: bool = False,
        startup_timeout: float = 5.0,
    ) -> DaemonHandle:
        if self._handle and self._handle.is_running():
            raise FastPipeError("Daemon is already running for this service")
        endpoints = self._server.snapshot_registry()
        if not endpoints:
            raise FastPipeError("Cannot run daemon without at least one registered endpoint")

        self._server.set_frozen(True)
        self._server.stop()

        def _cleanup(handle: DaemonHandle) -> None:
            if self._handle is handle:
                self._handle = None
            _unregister_daemon_handle(handle)
            self._server.set_frozen(False)

        process = _spawn_daemon_process(self._server.name, endpoints, poll_interval)
        handle = DaemonHandle(self._server.name, process, cleanup=_cleanup)
        try:
            _await_service_start(self._server.name, timeout=startup_timeout)
        except Exception:
            handle.stop(timeout=0.5)
            raise
        self._handle = handle
        _register_daemon_handle(handle)

        if wait:
            try:
                process.join()
            except KeyboardInterrupt:
                handle.stop()
        return handle


def create_service(name: str) -> ServiceBuilder:
    server = ServiceServer(name=name)
    return ServiceBuilder(server)


def _spawn_daemon_process(
    name: str, endpoints: List[EndpointSpec], poll_interval: float
) -> multiprocessing.Process:
    try:
        ctx = multiprocessing.get_context("fork")
    except ValueError:
        ctx = multiprocessing.get_context("spawn")
    process = ctx.Process(
        target=_daemon_worker,
        args=(name, endpoints, poll_interval),
        daemon=False,
        name=f"FastPIPE-daemon[{name}]",
    )
    process.start()
    return process


def _daemon_worker(name: str, endpoints: List[EndpointSpec], poll_interval: float) -> None:
    server = ServiceServer(name)
    for endpoint_name, func in endpoints:
        server.register(endpoint_name, func)
    server.run_forever(poll_interval=poll_interval)


def _await_service_start(name: str, *, timeout: float) -> None:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            resolve_service(name)
            return
        except ServiceNotFound:
            time.sleep(0.05)
    raise FastPipeError(f"Service '{name}' did not start within {timeout:.1f}s")
