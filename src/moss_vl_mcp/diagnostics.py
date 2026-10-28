"""Lightweight setup hints; never load a checkpoint or contact a remote service."""

import importlib.util
from typing import Any

from .config import Settings


def _missing_modules(names: tuple[str, ...]) -> list[str]:
    """Detect missing optional imports without importing GPU-heavy dependencies."""
    missing = []
    for name in names:
        try:
            installed = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            installed = False
        if not installed:
            missing.append(name)
    return missing


def check_setup(settings: Settings) -> dict[str, Any]:
    """Return explicitly non-authoritative local prerequisites for MCP clients."""
    offline_missing = _missing_modules(("torch", "transformers", "accelerate", "PIL"))
    screen_missing = _missing_modules(("mss", "PIL"))
    return {
        "media_root": str(settings.media_root),
        "media_root_exists": settings.media_root.is_dir(),
        "offline_python_modules_detected": not offline_missing,
        "offline_missing_modules": offline_missing,
        "screen_capture_enabled": settings.allow_screen_capture,
        "screen_python_modules_detected": not screen_missing,
        "screen_missing_modules": screen_missing,
        "server_video_replay_enabled": settings.allow_server_video,
        "not_checked": [
            "GPU availability or model checkpoint compatibility",
            "Actual offline inference",
            "Realtime WebSocket connection or backend readiness",
            "Operating-system screen capture permissions",
        ],
    }
