"""WebSocket protocol adapter and in-memory session registry for upstream Realtime.

This targets OpenMOSS reference /v1/realtime, NOT SGLang-Omni's different protocol.
"""

import asyncio
import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import websockets


@dataclass
class RealtimeSession:
    id: str
    websocket: Any
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=500))
    task: asyncio.Task[None] | None = None
    seq: int = 0
    last_timestamp: float = -1.0
    started_monotonic: float = field(default_factory=time.monotonic)
    closed: bool = False
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def record(self, message: dict[str, Any]) -> None:
        self.seq += 1
        self.events.append({"seq": self.seq, **message})


class RealtimeSessionManager:
    """Session Factory + Registry; each session owns one upstream WebSocket."""

    def __init__(self, url: str, max_sessions: int = 1) -> None:
        if max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        if not url.startswith(("ws://", "wss://")):
            raise ValueError("Realtime URL must be a WebSocket URL")
        self.url = url
        self.max_sessions = max_sessions
        self._sessions: dict[str, RealtimeSession] = {}
        self._lock = asyncio.Lock()

    def _get(self, session_id: str) -> RealtimeSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("Unknown session ID")
        if session.closed:
            raise RuntimeError("Realtime session is closed")
        return session

    async def start(self, prompt: str = "Describe important visual changes.") -> str:
        async with self._lock:
            # A disconnected WebSocket must not permanently consume model capacity.
            for stale_id, stale in list(self._sessions.items()):
                if stale.closed:
                    del self._sessions[stale_id]
            if len(self._sessions) >= self.max_sessions:
                raise RuntimeError("Realtime session limit reached")
            ws = await websockets.connect(self.url, open_timeout=15, max_size=2**22)
            try:
                await ws.send(json.dumps({
                    "type": "start",
                    "system_prompt": "You are a realtime visual observation assistant.",
                    "prompt": prompt,
                    "frame_queue_size": 256,
                    "max_tokens_per_second": 12,
                    "max_new_tokens": 4096,
                    "do_sample": False,
                    "repetition_penalty": 1.0,
                }))
                answer = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                if answer.get("type") != "ready":
                    raise RuntimeError(f"Realtime backend did not become ready: {answer}")
            except BaseException:
                await ws.close()
                raise
            session_id = uuid4().hex
            session = RealtimeSession(id=session_id, websocket=ws)
            self._sessions[session_id] = session
            session.record({"type": "ready"})
            session.task = asyncio.create_task(self._read_loop(session))
            return session_id

    async def _read_loop(self, session: RealtimeSession) -> None:
        try:
            async for message in session.websocket:
                if not isinstance(message, str):
                    continue
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    session.record({"type": "protocol_error", "message": "Invalid JSON"})
                    continue
                if isinstance(payload, dict):
                    session.record(payload)
        except asyncio.CancelledError:
            raise
        except (websockets.exceptions.WebSocketException, OSError) as exc:
            session.record({"type": "connection_error", "message": str(exc)})
        finally:
            session.closed = True
            session.record({"type": "disconnected"})
            await session.websocket.close()

    def frame_timestamp(self, session_id: str) -> float:
        """Seconds in the session stream, clamped to the previous frame timestamp."""
        session = self._get(session_id)
        return max(session.last_timestamp, time.monotonic() - session.started_monotonic)

    async def ask(self, session_id: str, prompt: str) -> None:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        session = self._get(session_id)
        async with session.send_lock:
            await session.websocket.send(json.dumps({"type": "prompt", "text": prompt}))

    async def push_frame(
        self, session_id: str, data: bytes, timestamp: float, prompt: str = ""
    ) -> None:
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("timestamp must be a nonnegative finite number")
        session = self._get(session_id)
        async with session.send_lock:
            if timestamp < session.last_timestamp:
                raise ValueError("frame timestamps must be non-decreasing")
            payload: dict[str, Any] = {"type": "frame", "timestamp": timestamp}
            if prompt:
                payload["prompt"] = prompt
            await session.websocket.send(json.dumps(payload))
            await session.websocket.send(data)
            session.last_timestamp = timestamp

    async def replay_video(
        self, session_id: str, path: Path, sample_fps: float = 1.0,
        max_frames: int = 256
    ) -> None:
        if not 0 < sample_fps <= 30 or not 0 <= max_frames <= 10000:
            raise ValueError("sample_fps/max_frames outside allowed range")
        session = self._get(session_id)
        async with session.send_lock:
            await session.websocket.send(json.dumps({
                "type": "video", "path": str(path), "sample_fps": sample_fps,
                "playback_speed": 1, "max_frames": max_frames,
            }))

    async def stop_video(self, session_id: str) -> None:
        session = self._get(session_id)
        async with session.send_lock:
            await session.websocket.send(json.dumps({"type": "stop_video"}))

    def events(self, session_id: str, after_seq: int = 0, limit: int = 50) -> dict[str, Any]:
        if after_seq < 0 or not 1 <= limit <= 500:
            raise ValueError("after_seq or limit invalid")
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("Unknown session ID")
        oldest = session.events[0]["seq"] if session.events else session.seq + 1
        pending = [event for event in session.events if event["seq"] > after_seq]
        data = pending[:limit]
        return {
            "session_id": session.id, "closed": session.closed,
            "latest_seq": session.seq,
            "next_seq": data[-1]["seq"] if data else after_seq,
            "has_more": len(pending) > limit,
            "history_gap": after_seq < oldest - 1,
            "events": data,
        }

    async def stop(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is None:
            raise ValueError("Unknown session ID")
        try:
            async with session.send_lock:
                if not session.closed:
                    await session.websocket.send(json.dumps({"type": "stop"}))
        finally:
            await session.websocket.close()
            if session.task is not None:
                session.task.cancel()
                await asyncio.gather(session.task, return_exceptions=True)
            session.closed = True
