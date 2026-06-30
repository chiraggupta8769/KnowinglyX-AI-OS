"""
Typed result envelope — every tool / service call returns one of these.
Callers MUST access .result via the property, which raises if success=False.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class ToolResult:
    success: bool
    tool: str
    duration_ms: float
    error: str | None = None
    side_effects: list[str] = field(default_factory=list)
    _result: Any = field(default=None, repr=False)

    @property
    def result(self) -> Any:
        if not self.success:
            raise RuntimeError(
                f"Tool '{self.tool}' failed — access .error instead. "
                f"Error: {self.error}"
            )
        return self._result

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "tool": self.tool,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "side_effects": self.side_effects,
            "result": self._result if self.success else None,
        }


def ok(tool: str, result: Any, duration_ms: float, side_effects: list[str] | None = None) -> ToolResult:
    return ToolResult(
        success=True,
        tool=tool,
        duration_ms=duration_ms,
        _result=result,
        side_effects=side_effects or [],
    )


def err(tool: str, error: str, duration_ms: float, side_effects: list[str] | None = None) -> ToolResult:
    return ToolResult(
        success=False,
        tool=tool,
        duration_ms=duration_ms,
        error=error,
        side_effects=side_effects or [],
    )


class timer:
    """Context manager that measures elapsed ms."""
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000

    @property
    def ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000
