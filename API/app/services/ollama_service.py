"""
Ollama service — reliable async wrapper with:
- Two-tier error handling: connection refused (permanent) vs timeout (transient)
- Retry budget: 2 retries on transient failures, immediate halt on permanent
- Per-chunk heartbeat timeout for streaming
- Typed return: (content: str, error: str | None)
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
REQUEST_TIMEOUT = 30.0
CHUNK_TIMEOUT = 10.0
RETRY_BUDGET = 2
RETRY_BACKOFF = 2.0  # seconds


class OllamaError(Exception):
    """Raised when Ollama fails after all retries are exhausted."""
    def __init__(self, message: str, permanent: bool = False):
        super().__init__(message)
        self.permanent = permanent


class OllamaService:
    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        request_timeout: float = REQUEST_TIMEOUT,
        chunk_timeout: float = CHUNK_TIMEOUT,
        retry_budget: int = RETRY_BUDGET,
    ):
        self._base_url = base_url
        self._request_timeout = request_timeout
        self._chunk_timeout = chunk_timeout
        self._retry_budget = retry_budget

    async def chat(self, prompt: str, model: str = "gemma3:4b") -> str:
        """
        Send a prompt and return the full response text.
        Raises OllamaError on permanent failure.
        """
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        last_error: str = ""
        for attempt in range(self._retry_budget + 1):
            try:
                async with httpx.AsyncClient(base_url=self._base_url) as client:
                    response = await asyncio.wait_for(
                        client.post("/api/chat", json=payload),
                        timeout=self._request_timeout,
                    )
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]

            except httpx.ConnectError as exc:
                # Permanent: Ollama is not running
                raise OllamaError(
                    f"Ollama is not running at {self._base_url}: {exc}",
                    permanent=True,
                ) from exc

            except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
                last_error = f"Timeout on attempt {attempt + 1}: {exc}"
                logger.warning("Ollama timeout (attempt %d/%d): %s", attempt + 1, self._retry_budget + 1, exc)
                if attempt < self._retry_budget:
                    await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
                    continue

            except httpx.HTTPStatusError as exc:
                last_error = f"HTTP {exc.response.status_code}: {exc}"
                if attempt < self._retry_budget:
                    await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
                    continue

            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt < self._retry_budget:
                    await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
                    continue

        raise OllamaError(f"Ollama failed after {self._retry_budget + 1} attempts: {last_error}")

    async def stream_chat(
        self, prompt: str, model: str = "gemma3:4b"
    ) -> AsyncIterator[str]:
        """
        Stream tokens from Ollama. Applies per-chunk heartbeat timeout.
        Yields string chunks. Raises OllamaError on failure.
        """
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }

        import json as _json

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=None) as client:
                async with client.stream("POST", "/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in self._iter_lines_with_heartbeat(response):
                        if not line.strip():
                            continue
                        try:
                            data = _json.loads(line)
                        except _json.JSONDecodeError:
                            continue
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done"):
                            break

        except httpx.ConnectError as exc:
            raise OllamaError(
                f"Ollama is not running at {self._base_url}: {exc}",
                permanent=True,
            ) from exc
        except OllamaError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise OllamaError(f"Streaming failed: {exc}") from exc

    async def _iter_lines_with_heartbeat(self, response: httpx.Response) -> AsyncIterator[str]:
        """Yield lines from the response, enforcing per-line heartbeat timeout."""
        buffer = ""
        async for chunk in self._aiter_bytes_with_heartbeat(response):
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                yield line
        if buffer:
            yield buffer

    async def _aiter_bytes_with_heartbeat(self, response: httpx.Response) -> AsyncIterator[bytes]:
        """Iterate over raw bytes with a per-chunk timeout."""
        async def _next_chunk(aiter):
            return await aiter.__anext__()

        aiter = response.aiter_bytes().__aiter__()
        while True:
            try:
                chunk = await asyncio.wait_for(_next_chunk(aiter), timeout=self._chunk_timeout)
                yield chunk
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError as exc:
                raise OllamaError(
                    f"Ollama stream stalled — no data for {self._chunk_timeout}s"
                ) from exc


ollama_service = OllamaService()
