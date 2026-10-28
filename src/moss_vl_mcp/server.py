"""Thin MCP transport layer; business logic lives in backend adapters."""

from mcp.server import MCPServer

from .capture import ScreenObserver
from .config import Settings
from .diagnostics import check_setup
from .media import (
    IMAGE_SUFFIXES,
    STREAM_IMAGE_SUFFIXES,
    VIDEO_SUFFIXES,
    resolve_media,
)
from .offline import OfflineVisionBackend
from .realtime import RealtimeSessionManager

UI_PROMPT = (
    "Act as a visual QA reviewer. Describe the interface, visible defects, "
    "unexpected states, accessibility concerns, and concrete reproduction clues. "
    "Distinguish observed evidence from hypotheses."
)
VIDEO_QA_PROMPT = (
    "Review this screen recording as a software QA engineer. Describe user actions "
    "in order and any observed UI regressions, with approximate timestamps "
    "where possible. Do not invent events that are not visible."
)


def create_server(
    settings: Settings | None = None,
    offline: OfflineVisionBackend | None = None,
    realtime: RealtimeSessionManager | None = None,
) -> MCPServer:
    """Composition root: inject adapters for testing or alternative inference engines."""
    settings = settings or Settings.from_env()
    offline = offline or OfflineVisionBackend(settings.offline_checkpoint)
    realtime = realtime or RealtimeSessionManager(
        settings.realtime_url, settings.max_sessions, settings.max_frame_bytes
    )
    screen = ScreenObserver(realtime, enabled=settings.allow_screen_capture)
    mcp = MCPServer("moss-vl-mcp")

    @mcp.tool()
    async def check_moss_vl_setup() -> dict:
        """Inspect local prerequisites without loading a model or connecting to the GPU backend."""
        return check_setup(settings)

    @mcp.tool()
    async def analyze_image(path: str, prompt: str = "Describe this image.") -> str:
        """Analyze a local image from MOSS_VL_MEDIA_ROOT using MOSS-VL-Instruct."""
        image = resolve_media(path, settings.media_root, IMAGE_SUFFIXES)
        return await offline.analyze(prompt, images=[str(image)])

    @mcp.tool()
    async def analyze_video(path: str, prompt: str = "Summarize this video.") -> str:
        """Analyze a completed local video using the offline MOSS-VL backend."""
        video = resolve_media(path, settings.media_root, VIDEO_SUFFIXES)
        return await offline.analyze(prompt, videos=[str(video)])

    @mcp.tool()
    async def inspect_ui(path: str) -> str:
        """Visual QA inspection of a screenshot; observations require agent verification."""
        image = resolve_media(path, settings.media_root, IMAGE_SUFFIXES)
        return await offline.analyze(UI_PROMPT, images=[str(image)])

    @mcp.tool()
    async def analyze_test_recording(path: str) -> str:
        """Review a Playwright or other screen recording for UI issues."""
        video = resolve_media(path, settings.media_root, VIDEO_SUFFIXES)
        return await offline.analyze(VIDEO_QA_PROMPT, videos=[str(video)])

    @mcp.tool()
    async def compare_ui_states(before_path: str, after_path: str) -> str:
        """Ask the VLM to compare two screenshots; not a pixel-perfect diff."""
        before = resolve_media(before_path, settings.media_root, IMAGE_SUFFIXES)
        after = resolve_media(after_path, settings.media_root, IMAGE_SUFFIXES)
        return await offline.analyze(
            "Compare image 1 (before) and image 2 (after). Identify visible changes, "
            "possible regressions, and what cannot be determined visually.",
            images=[str(before), str(after)],
        )

    @mcp.tool()
    async def start_visual_session(
        prompt: str = "Describe important visual changes."
    ) -> dict[str, str]:
        """Start one realtime observation session on the configured upstream WebSocket."""
        return {"session_id": await realtime.start(prompt)}

    @mcp.tool()
    async def ask_visual_session(session_id: str, prompt: str) -> dict[str, str]:
        """Ask while visual frames arrive; fetch subsequent output with get_visual_events."""
        await realtime.ask(session_id, prompt)
        return {"status": "queued", "session_id": session_id}

    @mcp.tool()
    async def push_visual_frame(
        session_id: str, path: str, timestamp: float, prompt: str = ""
    ) -> dict[str, str]:
        """Push one local JPEG/PNG frame with a non-decreasing stream timestamp."""
        image = resolve_media(path, settings.media_root, STREAM_IMAGE_SUFFIXES)
        if image.stat().st_size > settings.max_frame_bytes:
            raise ValueError("Image exceeds configured maximum frame size")
        await realtime.push_frame(session_id, image.read_bytes(), timestamp, prompt)
        return {"status": "sent", "session_id": session_id}

    @mcp.tool()
    async def replay_visual_video(
        session_id: str, path: str, sample_fps: float = 1.0,
        max_frames: int = 256,
    ) -> dict[str, str]:
        """Start backend-local real-time video replay (explicit opt-in required)."""
        if not settings.allow_server_video:
            raise ValueError("Set MOSS_VL_ALLOW_SERVER_VIDEO=1 to enable server-local replay")
        video = resolve_media(path, settings.media_root, VIDEO_SUFFIXES)
        await realtime.replay_video(session_id, video, sample_fps, max_frames)
        return {"status": "requested", "session_id": session_id}

    @mcp.tool()
    async def stop_visual_video(session_id: str) -> dict[str, str]:
        """Stop backend-local video playback but preserve the realtime session."""
        await realtime.stop_video(session_id)
        return {"status": "requested", "session_id": session_id}

    @mcp.tool()
    async def get_visual_events(
        session_id: str, after_seq: int = 0, limit: int = 50
    ) -> dict:
        """Fetch sequenced incremental model outputs and upstream status messages."""
        return realtime.events(session_id, after_seq, limit)

    @mcp.tool()
    async def start_screen_observation(
        session_id: str,
        monitor_index: int = 1,
        fps: float = 1.0,
        duration_seconds: float = 60.0,
    ) -> dict:
        """Capture a local display continuously (opt-in) into a realtime session."""
        return await screen.start(session_id, monitor_index, fps, duration_seconds)

    @mcp.tool()
    async def get_screen_observation_status(session_id: str) -> dict:
        """Report frame count and capture state, including any capture error."""
        return screen.status(session_id)

    @mcp.tool()
    async def stop_screen_observation(session_id: str) -> dict:
        """Stop the display producer without closing the realtime model session."""
        return await screen.stop(session_id)

    @mcp.tool()
    async def stop_visual_session(session_id: str) -> dict[str, str]:
        """Close a realtime observation session and free its upstream connection."""
        await screen.stop_if_active(session_id)
        await realtime.stop(session_id)
        return {"status": "stopped", "session_id": session_id}

    return mcp


def main() -> None:
    create_server().run()
