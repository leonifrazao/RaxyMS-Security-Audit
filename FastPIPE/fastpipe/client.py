"""Client-side proxies for connecting to FastPIPE services via filesystem messaging."""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List

from .exceptions import RemoteExecutionError, ServiceNotFound
from .registry import ServiceRecord, resolve_service


class ServiceClient:
    """Dynamic proxy that forwards attribute access to remote endpoints."""

    def __init__(
        self,
        name: str,
        *ctor_args: Any,
        timeout: float = 5.0,
        poll_interval: float = 0.01,
        **ctor_kwargs: Any,
    ) -> None:
        self._name = name
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._ctor_args = list(ctor_args)
        self._ctor_kwargs = dict(ctor_kwargs)
        self._record = resolve_service(name)
        self._root = Path(self._record.root)
        self._requests = self._root / "requests"
        self._responses = self._root / "responses"
        if not self._requests.exists() or not self._responses.exists():
            raise RemoteExecutionError(
                f"Service '{name}' directories are missing; is the service running?"
            )
        self._endpoints: List[str] = self._fetch_endpoints()

    def _write_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request_id = payload.setdefault("id", uuid.uuid4().hex)
        request_path = self._requests / f"{request_id}.json"
        tmp = request_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, request_path)

        response_path = self._responses / f"{request_id}.json"
        deadline = time.perf_counter() + self._timeout
        while time.perf_counter() < deadline:
            if response_path.exists():
                raw = response_path.read_text(encoding="utf-8")
                try:
                    response = json.loads(raw)
                finally:
                    try:
                        response_path.unlink()
                    except FileNotFoundError:
                        pass
                return response
            time.sleep(self._poll_interval)
        raise RemoteExecutionError(
            f"Timeout waiting for response from service '{self._name}' after {self._timeout}s"
        )

    def _fetch_endpoints(self) -> List[str]:
        response = self._write_request({"type": "list_endpoints"})
        if response.get("status") != "ok":
            raise RemoteExecutionError(f"Unable to query endpoints: {response}")
        return list(response.get("result", []))

    def __getattr__(self, name: str) -> Callable[..., Any]:
        def call_remote(*args: Any, **kwargs: Any) -> Any:
            payload = {
                "type": "call",
                "endpoint": name,
                "args": args,
                "kwargs": kwargs,
                "ctor_args": self._ctor_args,
                "ctor_kwargs": self._ctor_kwargs,
            }
            response = self._write_request(payload)
            if response.get("status") == "ok":
                return response.get("result")
            error = response.get("error", {})
            raise RemoteExecutionError(
                f"Remote call to '{name}' failed: {error.get('type')}: {error.get('message')}"
            )

        return call_remote

    def endpoints(self) -> List[str]:
        return list(self._endpoints)


def connect_service(
    name: str,
    *ctor_args: Any,
    timeout: float = 5.0,
    poll_interval: float = 0.01,
    **ctor_kwargs: Any,
) -> ServiceClient:
    try:
        return ServiceClient(
            name,
            *ctor_args,
            timeout=timeout,
            poll_interval=poll_interval,
            **ctor_kwargs,
        )
    except ServiceNotFound as exc:
        raise ServiceNotFound(f"Unable to connect to service '{name}': {exc}")
