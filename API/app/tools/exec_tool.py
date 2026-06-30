"""
Code execution tool — runs a command in a subprocess.
- Uses asyncio.create_subprocess_exec (not shell=True)
- Streams stdout/stderr with a per-read timeout and 10MB cap
- Kills the entire process group on timeout
- Never uses communicate() (avoids memory exhaustion)
"""
from __future__ import annotations

import asyncio
import os
import signal
import time
from typing import AsyncIterator

from app.utils.envelope import ToolResult, ok, err

MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE = 4096
DEFAULT_TIMEOUT = 30.0
CHUNK_TIMEOUT = 5.0  # max wait between output chunks


async def _read_stream(
    stream: asyncio.StreamReader,
    max_bytes: int = MAX_OUTPUT_BYTES,
    chunk_timeout: float = CHUNK_TIMEOUT,
) -> bytes:
    """Read from an asyncio stream with a per-chunk timeout and byte cap."""
    chunks: list[bytes] = []
    total = 0
    while total < max_bytes:
        try:
            chunk = await asyncio.wait_for(stream.read(CHUNK_SIZE), timeout=chunk_timeout)
        except asyncio.TimeoutError:
            break
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


async def exec_code(
    command: list[str],
    cwd: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    env: dict[str, str] | None = None,
) -> ToolResult:
    """
    Execute `command` as a subprocess.

    Args:
        command: e.g. ["python3", "script.py"] — NOT a shell string
        cwd: working directory for the process
        timeout: wall-clock timeout in seconds
        env: optional environment variables (merged with os.environ)

    Returns:
        ToolResult with result={"stdout": str, "stderr": str, "returncode": int}
    """
    t0 = time.perf_counter()
    proc = None

    merged_env = {**os.environ, **(env or {})}

    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=merged_env,
            # detached=False is the default — child belongs to our process group
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                asyncio.gather(
                    _read_stream(proc.stdout),
                    _read_stream(proc.stderr),
                ),
                timeout=timeout,
            )
            await proc.wait()

        except asyncio.TimeoutError:
            # Kill the entire process group (catches grandchildren too)
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                proc.kill()
            await proc.wait()

            duration_ms = (time.perf_counter() - t0) * 1000
            return err(
                tool="exec_code",
                error=f"Process timed out after {timeout}s",
                duration_ms=duration_ms,
                side_effects=["process_group_killed", "grandchild_orphan_possible"],
            )

        duration_ms = (time.perf_counter() - t0) * 1000
        return ok(
            tool="exec_code",
            result={
                "stdout": stdout_bytes.decode("utf-8", errors="replace"),
                "stderr": stderr_bytes.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
                "truncated": len(stdout_bytes) >= MAX_OUTPUT_BYTES or len(stderr_bytes) >= MAX_OUTPUT_BYTES,
            },
            duration_ms=duration_ms,
        )

    except FileNotFoundError:
        return err(
            tool="exec_code",
            error=f"Command not found: '{command[0]}'",
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        return err(
            tool="exec_code",
            error=str(exc),
            duration_ms=(time.perf_counter() - t0) * 1000,
            side_effects=["partial_side_effects_possible"],
        )
