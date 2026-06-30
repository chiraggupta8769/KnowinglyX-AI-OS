"""
safe_serialize — JSON serialization that doesn't crash on edge cases.
Handles: circular refs, BigInt (Python int is unbounded), NaN/Infinity,
         bytes, sets, non-serializable objects.
"""
import json
import math
from typing import Any


def safe_serialize(obj: Any, _seen: set | None = None) -> Any:
    """Recursively convert obj to a JSON-safe value."""
    if _seen is None:
        _seen = set()

    obj_id = id(obj)

    # Circular reference
    if isinstance(obj, (dict, list)):
        if obj_id in _seen:
            return "[Circular]"
        _seen.add(obj_id)

    try:
        if obj is None:
            return None
        if isinstance(obj, bool):
            return obj
        if isinstance(obj, int):
            # Python ints are unbounded; JS JSON can't handle > 2^53
            if obj > 2**53 or obj < -(2**53):
                return str(obj)
            return obj
        if isinstance(obj, float):
            if math.isnan(obj):
                return None
            if math.isinf(obj):
                return None
            return obj
        if isinstance(obj, str):
            return obj
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, (set, frozenset)):
            return [safe_serialize(v, _seen) for v in obj]
        if isinstance(obj, dict):
            result = {str(k): safe_serialize(v, _seen) for k, v in obj.items()}
            _seen.discard(obj_id)
            return result
        if isinstance(obj, (list, tuple)):
            result = [safe_serialize(v, _seen) for v in obj]
            _seen.discard(obj_id)
            return result
        # Try standard JSON serialization first
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return f"[NonSerializable:{type(obj).__name__}]"


def safe_json_dumps(obj: Any) -> str:
    """Serialize obj to a JSON string, never raising."""
    return json.dumps(safe_serialize(obj))
