"""Continuous screen producer tests using an injected capture adapter."""

import asyncio

import pytest

from moss_vl_mcp.capture import ScreenObserver


class StubRealtime:
    def __init__(self):
        self.frames = []
        self.received = asyncio.Event()

    def frame_timestamp(self, session_id):
        assert session_id == "session-1"
        return float(len(self.frames))

    async def push_frame(self, session_id, data, timestamp):
        self.frames.append((session_id, data, timestamp))
        self.received.set()


@pytest.mark.asyncio
async def test_screen_capture_disabled_by_default():
    service = ScreenObserver(StubRealtime(), capture=lambda _: b"jpeg")
    with pytest.raises(ValueError, match="disabled"):
        await service.start("session-1")


@pytest.mark.asyncio
async def test_screen_observation_sends_frames_until_stopped():
    realtime = StubRealtime()
    service = ScreenObserver(realtime, enabled=True, capture=lambda _: b"jpeg")

    started = await service.start("session-1", fps=2.0, duration_seconds=10.0)
    assert started["status"] == "running"
    await asyncio.wait_for(realtime.received.wait(), timeout=2.0)

    stopped = await service.stop("session-1")
    assert stopped["status"] == "stopped"
    assert stopped["sent_frames"] >= 1
    assert realtime.frames[0] == ("session-1", b"jpeg", 0.0)


@pytest.mark.asyncio
async def test_screen_observation_validates_bounds():
    service = ScreenObserver(StubRealtime(), enabled=True, capture=lambda _: b"jpeg")
    with pytest.raises(ValueError, match="fps"):
        await service.start("session-1", fps=30.0)
    with pytest.raises(ValueError, match="duration_seconds"):
        await service.start("session-1", duration_seconds=600.0)
    with pytest.raises(ValueError, match="monitor_index"):
        await service.start("session-1", monitor_index=0)


@pytest.mark.asyncio
async def test_screen_capture_errors_remain_observable():
    def broken_capture(_monitor):
        raise RuntimeError("display inaccessible")

    service = ScreenObserver(StubRealtime(), enabled=True, capture=broken_capture)
    await service.start("session-1")
    await asyncio.wait_for(service._tasks["session-1"], timeout=2.0)

    status = service.status("session-1")
    assert status["status"] == "error"
    assert "display inaccessible" in status["error"]
    await service.stop("session-1")
