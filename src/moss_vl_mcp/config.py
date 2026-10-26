"""Configuration is read once at server startup; no global mutable settings."""

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    media_root: Path
    offline_checkpoint: str = "OpenMOSS-Team/MOSS-VL-Instruct-0708"
    realtime_url: str = "ws://127.0.0.1:8000/v1/realtime"
    max_sessions: int = 1
    max_frame_bytes: int = 20 * 1024 * 1024
    allow_server_video: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            media_root=Path(os.getenv("MOSS_VL_MEDIA_ROOT", os.getcwd())).expanduser().resolve(),
            offline_checkpoint=os.getenv(
                "MOSS_VL_CHECKPOINT", "OpenMOSS-Team/MOSS-VL-Instruct-0708"
            ),
            realtime_url=os.getenv(
                "MOSS_VL_REALTIME_URL", "ws://127.0.0.1:8000/v1/realtime"
            ),
            max_sessions=int(os.getenv("MOSS_VL_MAX_SESSIONS", "1")),
            allow_server_video=os.getenv("MOSS_VL_ALLOW_SERVER_VIDEO", "0") == "1",
        )