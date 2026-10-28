import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from moss_vl_mcp.realtime import RealtimeSessionManager


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.inbox = asyncio.Queue()
        self.inbox.put_nowait('{"type":"ready"}')
        self.closed = False

    async def send(self, item):
        self.sent.append(item)

    async def recv(self):
        return await self.inbox.get()

    def __aiter__(self):
        return self

    async def __anext__(self):
        event = await self.inbox.get()
        if event is None:
            raise StopAsyncIteration
        return event

    async def close(self):
        self.closed = True
        self.inbox.put_nowait(None)


@pytest.mark.asyncio
async def test_realtime_lifecycle(monkeypatch):
    socket = FakeWebSocket()
    monkeypatch.setattr("moss_vl_mcp.realtime.websockets.connect", AsyncMock(return_value=socket))
    manager = RealtimeSessionManager("ws://localhost:8000/v1/realtime")
    sid = await manager.start("Watch the app")
    assert json.loads(socket.sent[0])["type"] == "start"
    with pytest.raises(RuntimeError, match="limit"):
        await manager.start()
    await manager.push_frame(sid, b"pngbytes", 1.5)
    assert json.loads(socket.sent[1]) == {"type": "frame", "timestamp": 1.5}
    assert socket.sent[2] == b"pngbytes"
    with pytest.raises(ValueError, match="non-decreasing"):
        await manager.push_frame(sid, b"pngbytes", 1.2)
    await manager.ask(sid, "What changed?")
    await socket.inbox.put('{"type":"output","text":"A dialog appeared."}')
    await asyncio.sleep(0)
    assert any(e.get("text") == "A dialog appeared." for e in manager.events(sid)["events"])
    await manager.stop(sid)
    assert socket.closed


@pytest.mark.asyncio
async def test_reject_bad_ready(monkeypatch):
    socket = FakeWebSocket()
    socket.inbox.get_nowait()
    socket.inbox.put_nowait('{"type":"error","message":"busy"}')
    monkeypatch.setattr("moss_vl_mcp.realtime.websockets.connect", AsyncMock(return_value=socket))
    manager = RealtimeSessionManager("ws://localhost:8000/v1/realtime")
    with pytest.raises(RuntimeError, match="did not become ready"):
        await manager.start()
    assert socket.closed


@pytest.mark.asyncio
async def test_upstream_seq_does_not_break_event_cursor(monkeypatch):
    socket = FakeWebSocket()
    monkeypatch.setattr("moss_vl_mcp.realtime.websockets.connect", AsyncMock(return_value=socket))
    manager = RealtimeSessionManager("ws://localhost:8000/v1/realtime")
    sid = await manager.start()

    # Only the MCP should set its pagination sequence; the upstream may send its own.
    await socket.inbox.put('{"type":"output","seq":9000,"text":"Frame described"}')
    await asyncio.sleep(0)

    first = manager.events(sid, after_seq=0, limit=1)
    assert first["latest_seq"] == 2
    assert first["next_seq"] == 1
    assert first["has_more"] is True
    assert first["history_gap"] is False
    second = manager.events(sid, after_seq=first["next_seq"])
    assert second["events"][0]["seq"] == 2
    assert second["events"][0]["text"] == "Frame described"
    assert second["next_seq"] == 2
    await manager.stop(sid)


@pytest.mark.asyncio
async def test_frame_guards_apply_to_all_realtime_producers(monkeypatch):
    socket = FakeWebSocket()
    monkeypatch.setattr("moss_vl_mcp.realtime.websockets.connect", AsyncMock(return_value=socket))
    with pytest.raises(ValueError, match="max_frame_bytes"):
        RealtimeSessionManager("ws://localhost:8000/v1/realtime", max_frame_bytes=0)

    manager = RealtimeSessionManager("ws://localhost:8000/v1/realtime", max_frame_bytes=4)
    sid = await manager.start()
    with pytest.raises(ValueError, match="empty"):
        await manager.push_frame(sid, b"", 0)
    with pytest.raises(ValueError, match="maximum"):
        await manager.push_frame(sid, b"12345", 0)
    assert len(socket.sent) == 1  # Invalid inputs must not send metadata or bytes.

    await manager.push_frame(sid, b"1234", 0)
    assert json.loads(socket.sent[1]) == {"type": "frame", "timestamp": 0}
    assert socket.sent[2] == b"1234"
    await manager.stop(sid)
