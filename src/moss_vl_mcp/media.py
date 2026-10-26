"""Restrict agent-supplied media paths to a configured local directory."""

from pathlib import Path

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})
STREAM_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})
VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi"})


class MediaPathError(ValueError):
    """Path is invalid or outside the configured media sandbox."""


def resolve_media(path: str, root: Path, suffixes: frozenset[str]) -> Path:
    if not path or "://" in path:
        raise MediaPathError("Provide a local filesystem path, not a URL")
    base = root.expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(base):
        raise MediaPathError(f"Media must be inside MOSS_VL_MEDIA_ROOT ({base})")
    if not resolved.is_file():
        raise MediaPathError(f"Media file does not exist: {resolved}")
    if resolved.suffix.lower() not in suffixes:
        raise MediaPathError(f"Unsupported media extension: {resolved.suffix}")
    return resolved
