from pathlib import Path
from unittest.mock import AsyncMock

from moss_vl_mcp.config import Settings
from moss_vl_mcp.server import create_server


def test_server_registration(tmp_path: Path):
    backend = AsyncMock()
    manager = AsyncMock()
    server = create_server(Settings(media_root=tmp_path), backend, manager)
    tools = server._tool_manager.list_tools()
    assert {t.name for t in tools} >= {
        "analyze_image", "analyze_video", "compare_ui_states", "inspect_ui",
        "analyze_test_recording", "start_visual_session", "push_visual_frame",
        "ask_visual_session", "get_visual_events", "stop_visual_session",
    }
