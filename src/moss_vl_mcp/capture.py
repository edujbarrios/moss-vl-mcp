"""Opt-in, bounded screen-frame producer for persistent MOSS-VL sessions.

Capture is disabled unless MOSS_VL_ALLOW_SCREEN_CAPTURE=1. The capture adapter is
injected for tests; Pillow and mss are only imported when local capture is used.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from .realtime import RealtimeSessionManager


class FrameCapture(Protocol):
    def __call__(self, monitor_index: int) -> bytes: ...


def capture_screen_jpeg(monitor_index: int) -> bytes:
    """Capture and compress one local display frame, without saving it to disk."""
    import mss
    from PIL import Image

    with mss.mss() as screen:
        if not 1 <= monitor_index < len(screen.monitors):
            raise ValueError(f"Unknown monitor index: {monitor_index}")
        screenshot = screen.grab(screen.monitors[monitor_index])
        image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        image.thumbnail((1280, 720))
        with io.BytesIO() as buffer:
            image.save(buffer, format="JPEG", quality=80)
            return buffer.getvalue()


@dataclass
class CaptureStatus:
    session_id: str
    status: str = "running"
    sent_frames: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "sent_frames": self.sent_frames,
            "error": self.error,
        }


class ScreenObserver:
    """Producer strategy; an asyncio task captures and sends bounded screen frames."""

    def __init__(
        self,
        realtime: RealtimeSessionManager,
        *,
        enabled: bool = False,
        capture: FrameCapture = capture_screen_jpeg,
    ) -> None:
        self.realtime = realtime
        self.enabled = enabled
        self.capture = capture
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._states: dict[str, CaptureStatus] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        session_id: str,
        monitor_index: int = 1,
        fps: float = 1.0,
        duration_seconds: float = 60.0,
    ) -> dict[str, str | int | None]:
        if not self.enabled:
            raise ValueError("Screen capture is disabled: set MOSS_VL_ALLOW_SCREEN_CAPTURE=1")
        if not 1 <= monitor_index <= 16:
            raise ValueError("monitor_index must be between 1 and 16")
        if not 0 < fps <= 2:
            raise ValueError("fps must be greater than 0 and at most 2")
        if not 0 < duration_seconds <= 300:
            raise ValueError("duration_seconds must be between 0 and 300")
        # Check availability up-front, before reporting that observation has started.
        if self.capture is capture_screen_jpeg and (
            importlib.util.find_spec("mss") is None
            or importlib.util.find_spec("PIL") is None
        ):
            raise RuntimeError("Screen capture requires: pip install 'moss-vl-mcp[screen]'")

        self.realtime._get(session_id)  # Fail immediately for absent/closed sessions.
        async with self._lock:
            task = self._tasks.get(session_id)
            if task is not None and not task.done():
                raise ValueError("Screen observation is already active for this session")
            state = CaptureStatus(session_id=session_id)
            self._states[session_id] = state
            self._tasks[session_id] = asyncio.create_task(
                self._run(state, monitor_index, fps, duration_seconds)
            )
            return state.to_dict()

    async def _run(
        self, state: CaptureStatus, monitor_index: int, fps: float, duration: float
    ) -> None:
        started = time.monotonic()
        interval = 1.0 / fps
        try:
            while time.monotonic() - started < duration:
                cycle = time.monotonic()
                jpeg = await asyncio.to_thread(self.capture, monitor_index)
                # Upstream reference protocol accepts timestamp + JPEG/PNG bytes.
                await self.realtime.push_frame(
                    state.session_id, jpeg, time.monotonic() - started
                )
                state.sent_frames += 1
                await asyncio.sleep(max(0.0, interval - (time.monotonic() - cycle)))
            state.status = "completed"
        except asyncio.CancelledError:
            state.status = "stopped"
            raise
        except Exception as exc:  # noqa: BLE001 - record any background task failure
            state.status = "error"
            state.error = f"{type(exc).__name__}: {exc}"

    def status(self, session_id: str) -> dict[str, str | int | None]:
        state = self._states.get(session_id)
        if state is None:
            raise ValueError("No screen observation has been started for this session")
        return state.to_dict()

    async def stop(self, session_id: str) -> dict[str, str | int | None]:
        async with self._lock:
            task = self._tasks.pop(session_id, None)
            state = self._states.get(session_id)
        if state is None:
            raise ValueError("No screen observation has been started for this session")
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return state.to_dict()

    async def stop_if_active(self, session_id: str) -> None:
        if session_id in self._states:
            await self.stop(session_id)
