"""
WebSocket agent endpoint — /ws/agent
- Typed chunk protocol: ready | chunk | done | error | heartbeat
- send-lock + client_state guard before every send
- stream_id per session
- Reconnect yields a new session (no resume — documented)
- Heartbeat every 15s to detect dead connections
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.tools import registry
from app.services.ollama_service import ollama_service, OllamaError
from app.utils.serializer import safe_json_dumps

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agent"])

HEARTBEAT_INTERVAL = 15.0  # seconds between server-side heartbeat pings


@router.websocket("/ws/agent")
async def agent_ws(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    send_lock = asyncio.Lock()

    async def safe_send(payload: dict) -> bool:
        """Send JSON to client with lock + state guard. Returns False if WS is closed."""
        async with send_lock:
            if websocket.client_state != WebSocketState.CONNECTED:
                return False
            try:
                await websocket.send_text(safe_json_dumps(payload))
                return True
            except Exception as exc:
                logger.warning("WS send failed (session=%s): %s", session_id, exc)
                return False

    # Announce ready
    await safe_send({"type": "ready", "session_id": session_id})

    # Heartbeat task
    async def heartbeat():
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            ok = await safe_send({"type": "heartbeat", "session_id": session_id})
            if not ok:
                break

    heartbeat_task = asyncio.create_task(heartbeat())

    try:
        while True:
            # Receive message from client
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            # Parse incoming message
            import json as _json
            try:
                message = _json.loads(raw)
            except _json.JSONDecodeError:
                await safe_send({
                    "type": "error",
                    "session_id": session_id,
                    "error": "Invalid JSON in request",
                })
                continue

            msg_type = message.get("type", "prompt")
            request_id = message.get("request_id", str(uuid.uuid4()))

            # --- Tool invocation ---
            if msg_type == "tool":
                tool_name = message.get("tool")
                args = message.get("args", {})

                if not tool_name:
                    await safe_send({
                        "type": "error",
                        "session_id": session_id,
                        "request_id": request_id,
                        "error": "Missing 'tool' field",
                    })
                    continue

                result = await registry.invoke(tool_name, args)
                await safe_send({
                    "type": "result",
                    "session_id": session_id,
                    "request_id": request_id,
                    "data": result.to_dict(),
                })

            # --- Streaming LLM prompt ---
            elif msg_type == "prompt":
                prompt = message.get("prompt", "")
                model = message.get("model", "gemma3:4b")

                if not prompt:
                    await safe_send({
                        "type": "error",
                        "session_id": session_id,
                        "request_id": request_id,
                        "error": "Missing 'prompt' field",
                    })
                    continue

                try:
                    async for chunk in ollama_service.stream_chat(prompt=prompt, model=model):
                        sent = await safe_send({
                            "type": "chunk",
                            "session_id": session_id,
                            "request_id": request_id,
                            "data": chunk,
                        })
                        if not sent:
                            break

                    await safe_send({
                        "type": "done",
                        "session_id": session_id,
                        "request_id": request_id,
                    })

                except OllamaError as exc:
                    await safe_send({
                        "type": "error",
                        "session_id": session_id,
                        "request_id": request_id,
                        "error": str(exc),
                        "permanent": exc.permanent,
                    })

            else:
                await safe_send({
                    "type": "error",
                    "session_id": session_id,
                    "request_id": request_id,
                    "error": f"Unknown message type '{msg_type}'. Expected: prompt | tool",
                })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("Unhandled error in WS session %s: %s", session_id, exc)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        logger.info("WS session %s closed", session_id)
