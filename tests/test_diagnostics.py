"""Setup checks are lightweight and must never require model weights or a GPU."""

from moss_vl_mcp import diagnostics
from moss_vl_mcp.config import Settings


def test_setup_reports_missing_modules_without_importing_them(monkeypatch, tmp_path):
    def fake_find_spec(name):
        return object() if name == "PIL" else None

    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", fake_find_spec)
    settings = Settings(media_root=tmp_path / "missing", allow_screen_capture=True)

    report = diagnostics.check_setup(settings)

    assert report["media_root_exists"] is False
    assert report["offline_python_modules_detected"] is False
    assert report["offline_missing_modules"] == ["torch", "transformers", "accelerate"]
    assert report["screen_capture_enabled"] is True
    assert report["screen_missing_modules"] == ["mss"]
    assert "Actual offline inference" in report["not_checked"]


def test_setup_reports_modules_but_does_not_claim_model_is_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", lambda _: object())
    report = diagnostics.check_setup(Settings(media_root=tmp_path))

    assert report["media_root_exists"] is True
    assert report["offline_python_modules_detected"] is True
    assert report["screen_python_modules_detected"] is True
    assert report["server_video_replay_enabled"] is False
    assert "GPU availability or model checkpoint compatibility" in report["not_checked"]


def test_setup_handles_modules_without_valid_spec(monkeypatch, tmp_path):
    def broken_find_spec(_):
        raise ValueError("module.__spec__ is None")

    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", broken_find_spec)
    report = diagnostics.check_setup(Settings(media_root=tmp_path))
    assert report["offline_missing_modules"] == ["torch", "transformers", "accelerate", "PIL"]
