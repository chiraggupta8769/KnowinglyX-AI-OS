"""
Groq LLM service — drop-in replacement for OllamaService.
Uses Groq's OpenAI-compatible API for fast cloud inference.
- Two-tier error handling: auth/config (permanent) vs timeout/rate-limit (transient)
- Retry budget: 2 retries on transient failures
- Streaming support with per-chunk heartbeat
- Model mapping: keeps familiar model names, maps to Groq equivalents
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
REQUEST_TIMEOUT = 60.0
CHUNK_TIMEOUT = 15.0
RETRY_BUDGET = 2
RETRY_BACKOFF = 2.0

# Map local model names → Groq model IDs
MODEL_MAP = {
    "gemma3:4b": "llama-3.1-8b-instant",
    "qwen3:8b": "llama-3.3-70b-versatile",
    "llama3": "llama-3.3-70b-versatile",
    "default": "llama-3.1-8b-instant",
}


class OllamaError(Exception):
    """Kept as OllamaError for compatibility — now wraps Groq errors."""
    def __init__(self, message: str, permanent: bool = False):
        super().__init__(message)
        self.permanent = permanent


def _resolve_model(model: str) -> str:
    return MODEL_MAP.get(model, MODEL_MAP["default"])


class OllamaService:
    """Groq-backed LLM service with the same interface as the original OllamaService."""

    def __init__(
        self,
        api_key: str | None = None,
        request_timeout: float = REQUEST_TIMEOUT,
        chunk_timeout: float = CHUNK_TIMEOUT,
        retry_budget: int = RETRY_BUDGET,
    ):
        self._api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self._request_timeout = request_timeout
        self._chunk_timeout = chunk_timeout
        self._retry_budget = retry_budget

        if not self._api_key:
            logger.warning("GROQ_API_KEY not set — requests will fail with 401")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, prompt: str, model: str = "gemma3:4b") -> str:
        """Send a prompt and return the full response text."""
        groq_model = _resolve_model(model)
        payload = {
            "model": groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        last_error = ""
        for attempt in range(self._retry_budget + 1):
            try:
                async with httpx.AsyncClient(base_url=GROQ_BASE_URL) as client:
                    response = await asyncio.wait_for(
                        client.post(
                            "/chat/completions",
                            json=payload,
                            headers=self._headers(),
                        ),
                        timeout=self._request_timeout,
                    )

                if response.status_code == 401:
                    raise OllamaError(
                        "Groq API key is invalid or missing. Set GROQ_API_KEY.",
                        permanent=True,
                    )
                if response.status_code == 429:
                    # Rate limited — transient
                    raise httpx.HTTPStatusError(
                        "Rate limited", request=response.request, response=response
                    )

                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]

            except OllamaError:
                raise
            except httpx.ConnectError as exc:
                raise OllamaError(
                    f"Cannot connect to Groq API: {exc}", permanent=True
                ) from exc
            except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
                last_error = f"Timeout on attempt {attempt + 1}: {exc}"
                logger.warning("Groq timeout (attempt %d/%d): %s", attempt + 1, self._retry_budget + 1, exc)
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

        raise OllamaError(f"Groq failed after {self._retry_budget + 1} attempts: {last_error}")

    async def stream_chat(
        self, prompt: str, model: str = "gemma3:4b"
    ) -> AsyncIterator[str]:
        """Stream tokens from Groq. Yields string chunks."""
        groq_model = _resolve_model(model)
        payload = {
            "model": groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }

        import json as _json

        try:
            async with httpx.AsyncClient(
                base_url=GROQ_BASE_URL, timeout=None
            ) as client:
                async with client.stream(
                    "POST",
                    "/chat/completions",
                    json=payload,
                    headers=self._headers(),
                ) as response:
                    if response.status_code == 401:
                        raise OllamaError(
                            "Groq API key is invalid or missing.", permanent=True
                        )
                    response.raise_for_status()

                    async for line in self._iter_lines_with_heartbeat(response):
                        line = line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        try:
                            data = _json.loads(line)
                        except _json.JSONDecodeError:
                            continue
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content

        except OllamaError:
            raise
        except httpx.ConnectError as exc:
            raise OllamaError(f"Cannot connect to Groq API: {exc}", permanent=True) from exc
        except Exception as exc:  # noqa: BLE001
            raise OllamaError(f"Streaming failed: {exc}") from exc

    async def _iter_lines_with_heartbeat(self, response: httpx.Response) -> AsyncIterator[str]:
        buffer = ""
        async for chunk in self._aiter_bytes_with_heartbeat(response):
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                yield line
        if buffer:
            yield buffer

    async def _aiter_bytes_with_heartbeat(self, response: httpx.Response) -> AsyncIterator[bytes]:
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
                    f"Groq stream stalled — no data for {self._chunk_timeout}s"
                ) from exc


ollama_service = OllamaService()
