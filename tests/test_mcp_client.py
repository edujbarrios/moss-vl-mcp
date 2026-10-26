"""In-memory MCP contract tests; do not load model weights or require a GPU."""

from __future__ import annotations

import pytest
from mcp import Client

from moss_vl_mcp.config import Settings
from moss_vl_mcp.server import create_server


class StubOffline:
    def __init__(self) -> None:
        self.calls = []

    async def analyze(self, prompt, *, images=None, videos=None, max_tokens=512):
        self.calls.append({"prompt": prompt, "images": images, "videos": videos})
        return "Observed visual content."


class StubRealtime:
    async def start(self, prompt=""):
        return "fake-session"

    async def ask(self, session_id, prompt):
        pass

    async def push_frame(self, session_id, data, timestamp, prompt=""):
        pass

    def events(self, session_id, after_seq=0, limit=50):
        return {"session_id": session_id, "latest_seq": 1, "events": []}

    async def stop(self, session_id):
        pass

    async def replay_video(self, session_id, path, sample_fps=1.0, max_frames=256):
        pass

    async def stop_video(self, session_id):
        pass


@pytest.mark.asyncio
async def test_tools_available_and_image_workflow(tmp_path):
    (tmp_path / "screen.png").write_bytes(b"fake image for adapter tests")
    (tmp_path / "flow.mp4").write_bytes(b"fake video for adapter tests")
    offline = StubOffline()
    mcp = create_server(
        Settings(media_root=tmp_path), offline=offline, realtime=StubRealtime()
    )

    async with Client(mcp, raise_exceptions=True) as client:
        catalog = await client.list_tools()
        names = {tool.name for tool in catalog.tools}
        assert {"analyze_image", "analyze_video", "inspect_ui", "compare_ui_states",
                "start_visual_session", "push_visual_frame", "ask_visual_session",
                "get_visual_events", "stop_visual_session"}.issubset(names)

        result = await client.call_tool(
            "analyze_image", {"path": "screen.png", "prompt": "What is visible?"}
        )
        assert not result.is_error
        assert "Observed visual content" in result.content[0].text
        assert offline.calls[-1]["images"] == [str(tmp_path / "screen.png")]

        result = await client.call_tool("analyze_video", {"path": "flow.mp4"})
        assert not result.is_error
        assert offline.calls[-1]["videos"] == [str(tmp_path / "flow.mp4")]

        result = await client.call_tool("start_visual_session", {})
        assert not result.is_error
        assert "fake-session" in str(result.content)

        result = await client.call_tool(
            "get_visual_events", {"session_id": "fake-session"}
        )
        assert not result.is_error


@pytest.mark.asyncio
async def test_mcp_rejects_media_outside_root(tmp_path):
    offline = StubOffline()
    server = create_server(
        Settings(media_root=tmp_path), offline=offline, realtime=StubRealtime()
    )
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "analyze_image", {"path": "../secrets.png"}
        )
        assert result.is_error
    assert offline.calls == []
