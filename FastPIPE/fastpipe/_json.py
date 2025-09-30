"""Fast JSON helpers with optional orjson acceleration."""
from __future__ import annotations

# Prefer fast orjson if available, with UTF-8 output
try:  # pragma: no cover - optional dependency
    import orjson  # type: ignore

    def dumps(obj) -> str:
        # orjson returns bytes, ensure str
        return orjson.dumps(obj, option=orjson.OPT_NON_STR_KEYS).decode("utf-8")

    def loads(s: str):
        # accepts str or bytes
        return orjson.loads(s)  # type: ignore[arg-type]

    HAS_ORJSON = True
except Exception:  # pragma: no cover - fallback path
    import json as _json

    def dumps(obj) -> str:
        # compact separators to reduce payload size
        return _json.dumps(obj, separators=(",", ":"))

    def loads(s: str):
        return _json.loads(s)

    HAS_ORJSON = False

__all__ = ["dumps", "loads", "HAS_ORJSON"]
