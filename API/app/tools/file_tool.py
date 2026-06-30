"""File creation / read tool."""
from __future__ import annotations

import os
import time

import aiofiles
import aiofiles.os

from app.utils.envelope import ToolResult, ok, err


async def file_create(
    path: str,
    content: str | bytes,
    encoding: str = "utf-8",
) -> ToolResult:
    """
    Create (or overwrite) a file at `path`.
    - Creates parent directories automatically.
    - Verifies the write succeeded.
    - Use encoding='binary' to write raw bytes.
    """
    t0 = time.perf_counter()
    try:
        parent = os.path.dirname(os.path.abspath(path))
        await aiofiles.os.makedirs(parent, exist_ok=True)

        if encoding == "binary":
            if isinstance(content, str):
                content = content.encode("utf-8")
            async with aiofiles.open(path, "wb") as f:
                await f.write(content)
        else:
            if isinstance(content, bytes):
                content = content.decode(encoding, errors="replace")
            async with aiofiles.open(path, "w", encoding=encoding) as f:
                await f.write(content)

        # Verify write
        stat = await aiofiles.os.stat(path)
        duration_ms = (time.perf_counter() - t0) * 1000
        return ok(
            tool="file_create",
            result={"path": path, "bytes": stat.st_size},
            duration_ms=duration_ms,
        )

    except PermissionError as exc:
        return err(
            tool="file_create",
            error=f"Permission denied writing to '{path}': {exc}",
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return err(
            tool="file_create",
            error=str(exc),
            duration_ms=(time.perf_counter() - t0) * 1000,
            side_effects=["partial_side_effects_possible"],
        )


async def file_read(path: str, encoding: str = "utf-8") -> ToolResult:
    """Read a file and return its contents."""
    t0 = time.perf_counter()
    try:
        if encoding == "binary":
            async with aiofiles.open(path, "rb") as f:
                content = await f.read()
            result_content = content.decode("utf-8", errors="replace")
        else:
            async with aiofiles.open(path, "r", encoding=encoding) as f:
                result_content = await f.read()

        return ok(
            tool="file_read",
            result={"path": path, "content": result_content},
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
    except FileNotFoundError:
        return err(
            tool="file_read",
            error=f"File not found: '{path}'",
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return err(
            tool="file_read",
            error=str(exc),
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
