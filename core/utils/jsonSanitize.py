from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def make_json_safe(value: Any) -> Any:
    """
    Convert Python objects into JSON-serializable structures in a strict, deterministic way.

    Goals:
    - Convert only known non-JSON types (datetime/date, UUID, Decimal, Enum, bytes).
    - Recurse through dict/list structures.
    - Fail fast on unknown objects (do NOT silently stringify everything).
    """

    # JSON primitives
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    # datetime/date -> ISO string
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    # UUID -> string
    if isinstance(value, UUID):
        return str(value)

    # Decimal -> float (or change to str(value) if you want exactness)
    if isinstance(value, Decimal):
        return float(value)

    # Enum -> underlying value
    if isinstance(value, Enum):
        return value.value

    # bytes -> utf-8 string (fallback to repr)
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except Exception:
            return repr(value)

    # dict -> sanitize keys+values
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            # JSON keys must be strings
            key = k if isinstance(k, str) else str(k)
            out[key] = make_json_safe(v)
        return out

    # list/tuple/set -> list
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(v) for v in value]

    # dataclass -> dict
    if is_dataclass(value):
        return make_json_safe(asdict(value))

    # Pydantic v2 models -> dict
    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        return make_json_safe(value.model_dump())

    # Common "to_dict" / "dict" patterns
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return make_json_safe(value.to_dict())
    if hasattr(value, "dict") and callable(getattr(value, "dict")):
        return make_json_safe(value.dict())

    # Fail fast (do not hide bugs)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable by make_json_safe")
