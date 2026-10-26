import pytest

from moss_vl_mcp.media import IMAGE_SUFFIXES, MediaPathError, resolve_media


def test_resolve_relative_and_absolute(tmp_path):
    file = tmp_path / "photo.PNG"
    file.write_bytes(b"test")
    assert resolve_media("photo.PNG", tmp_path, IMAGE_SUFFIXES) == file
    assert resolve_media(str(file), tmp_path, IMAGE_SUFFIXES) == file


def test_reject_escape(tmp_path):
    outside = tmp_path.parent / "outside.png"
    outside.write_bytes(b"test")
    try:
        with pytest.raises(MediaPathError, match="inside"):
            resolve_media(str(outside), tmp_path, IMAGE_SUFFIXES)
    finally:
        outside.unlink(missing_ok=True)


def test_reject_urls_and_unknown_types(tmp_path):
    (tmp_path / "secret.txt").write_text("no")
    with pytest.raises(MediaPathError):
        resolve_media("https://example.com/a.png", tmp_path, IMAGE_SUFFIXES)
    with pytest.raises(MediaPathError):
        resolve_media("secret.txt", tmp_path, IMAGE_SUFFIXES)
