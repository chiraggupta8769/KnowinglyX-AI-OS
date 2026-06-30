"""
ToolRegistry — async-safe tool invocation with:
- Per-invocation asyncio timeout
- Ring buffer trace (deque maxlen=1000)
- Async-safe trace writes via lock
- Typed ToolResult envelope on every path
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from typing import Any, Callable, Coroutine

from app.utils.envelope import ToolResult, ok, err


class ToolRegistry:
    def __init__(self, default_timeout: float = 30.0, trace_capacity: int = 1000):
        self._tools: dict[str, Callable[..., Coroutine]] = {}
        self._default_timeout = default_timeout
        self._trace: deque[dict] = deque(maxlen=trace_capacity)
        self._trace_lock = asyncio.Lock()

    def register(self, name: str, fn: Callable[..., Coroutine]) -> None:
        """Register an async tool function under the given name."""
        self._tools[name] = fn

    async def invoke(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> ToolResult:
        """
        Invoke a registered tool with full safety guarantees:
        - Unknown tool → ToolResult(success=False)
        - Timeout → ToolResult(success=False)
        - Exception → ToolResult(success=False)
        - Never raises.
        """
        invocation_id = str(uuid.uuid4())
        args = args or {}
        t0 = time.perf_counter()
        effective_timeout = timeout if timeout is not None else self._default_timeout

        if tool_name not in self._tools:
            result = err(
                tool=tool_name,
                error=f"Unknown tool '{tool_name}'. Registered: {list(self._tools)}",
                duration_ms=0.0,
            )
            await self._record(invocation_id, tool_name, args, result)
            return result

        try:
            raw = await asyncio.wait_for(
                self._tools[tool_name](**args),
                timeout=effective_timeout,
            )
            duration_ms = (time.perf_counter() - t0) * 1000

            if isinstance(raw, ToolResult):
                result = raw
                # Patch duration if the tool didn't measure it
                if result.duration_ms == 0.0:
                    object.__setattr__(result, "duration_ms", duration_ms)
            else:
                result = ok(tool=tool_name, result=raw, duration_ms=duration_ms)

        except asyncio.TimeoutError:
            duration_ms = (time.perf_counter() - t0) * 1000
            result = err(
                tool=tool_name,
                error=f"Tool timed out after {effective_timeout}s",
                duration_ms=duration_ms,
                side_effects=["partial_side_effects_possible"],
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - t0) * 1000
            result = err(
                tool=tool_name,
                error=str(exc),
                duration_ms=duration_ms,
                side_effects=["partial_side_effects_possible"],
            )

        await self._record(invocation_id, tool_name, args, result)
        return result

    async def _record(
        self,
        invocation_id: str,
        tool_name: str,
        args: dict,
        result: ToolResult,
    ) -> None:
        entry = {
            "id": invocation_id,
            "tool": tool_name,
            "args_keys": list(args.keys()),
            "success": result.success,
            "duration_ms": result.duration_ms,
            "error": result.error,
            "side_effects": result.side_effects,
        }
        async with self._trace_lock:
            self._trace.append(entry)

    def get_trace(self) -> list[dict]:
        """Return a snapshot of the trace ring buffer (newest last)."""
        return list(self._trace)

    @property
    def registered_tools(self) -> list[str]:
        return list(self._tools.keys())


# Singleton registry — import and use this in routes / services
registry = ToolRegistry()
