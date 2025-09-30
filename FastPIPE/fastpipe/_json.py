"""Fast JSON helpers with optional orjson acceleration."""
from __future__ import annotations

# Prefer fast orjson if available, with UTF-8 output
try:
    import orjson  # type: ignore
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "FastPIPE requires the 'orjson' package. Install it with: pip install orjson"
    ) from exc


def dumps(obj) -> str:
    # orjson returns bytes, ensure str
    return orjson.dumps(obj, option=orjson.OPT_NON_STR_KEYS).decode("utf-8")


def loads(s: str):
    # accepts str or bytes
    return orjson.loads(s)  # type: ignore[arg-type]


HAS_ORJSON = True

__all__ = ["dumps", "loads", "HAS_ORJSON"]
