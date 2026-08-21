"""Cache-busting and download-fallback behavior of download_video."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from yt_dlp.utils import DownloadError

import clipper
from clipper import (
    DOWNLOAD_PROFILE,
    download_video,
    reuse_cached_source,
    save_json,
)


def _write_cache(work_dir: Path, profile) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    source = work_dir / "source.mp4"
    source.write_bytes(b"fake video")
    meta = {"id": "x", "title": "x"}
    if profile is not None:
        meta["download_profile"] = profile
    save_json(work_dir / "metadata.json", meta)
    return source


def test_cache_with_current_profile_is_reused(tmp_path, monkeypatch):
    source = _write_cache(tmp_path, DOWNLOAD_PROFILE)
    monkeypatch.setattr(clipper, "get_video_size", lambda path: (1920, 1080))
    result = reuse_cached_source(tmp_path, tmp_path / "metadata.json")
    assert result is not None
    assert result[0] == source
    assert source.exists()


@pytest.mark.parametrize("stale_profile", [None, {"version": 1, "max_height": 1080}])
def test_stale_cache_is_deleted_and_not_reused(tmp_path, monkeypatch, stale_profile):
    source = _write_cache(tmp_path, stale_profile)
    monkeypatch.setattr(clipper, "get_video_size", lambda path: (1280, 720))
    assert reuse_cached_source(tmp_path, tmp_path / "metadata.json") is None
    assert not source.exists()


def test_no_cache_returns_none(tmp_path):
    assert reuse_cached_source(tmp_path, tmp_path / "metadata.json") is None


class _FakeYDL:
    """Records the opts of each construction; first extract fails on demand."""

    calls: list[dict] = []
    fail_first = True
    work_dir: Path

    def __init__(self, opts):
        self.opts = opts
        type(self).calls.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        if type(self).fail_first and len(type(self).calls) == 1:
            raise DownloadError("fragment 3 not found (not a 403)")
        source = type(self).work_dir / "source.mp4"
        source.write_bytes(b"video")
        return {"id": "x", "title": "x", "ext": "mp4", "width": 1920, "height": 1080}

    def prepare_filename(self, info):
        return str(type(self).work_dir / "source.mp4")


@pytest.fixture
def fake_ydl(tmp_path, monkeypatch):
    _FakeYDL.calls = []
    _FakeYDL.fail_first = True
    _FakeYDL.work_dir = tmp_path
    monkeypatch.setattr(clipper, "YoutubeDL", _FakeYDL)
    monkeypatch.setattr(clipper, "ffmpeg_path", lambda: "ffmpeg")
    return _FakeYDL


def test_any_download_error_triggers_conservative_retry(tmp_path, fake_ydl):
    # The old fallback only fired on "403" and forced bare "best" (progressive
    # only, can fail outright). Any DownloadError must retry, keeping the full
    # ladder but preferring plain https DASH.
    file_path, meta = download_video("https://example.invalid/v", tmp_path)

    assert len(fake_ydl.calls) == 2
    first, second = fake_ydl.calls
    assert first["format_sort"] == clipper.SOURCE_FORMAT_SORT
    assert second["format_sort"] == clipper.CONSERVATIVE_FORMAT_SORT
    assert second["extractor_args"] == {"youtube": {"player_client": ["android", "ios"]}}
    assert second["format"] == first["format"]  # full ladder, never bare "best"
    assert file_path.exists()


def test_fresh_download_stamps_the_profile(tmp_path, fake_ydl):
    fake_ydl.fail_first = False
    _, meta = download_video("https://example.invalid/v", tmp_path)

    assert meta["download_profile"] == DOWNLOAD_PROFILE
    on_disk = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert on_disk["download_profile"] == DOWNLOAD_PROFILE


def test_base_opts_do_not_restrict_formats():
    # A forced player_client list (+ mismatched User-Agent) made yt-dlp discard
    # every rendition above 360p, so sources were downloaded at 640x360 and
    # upscaled ~5.3x. Client switching belongs only in the download fallback.
    opts = clipper._ydl_base_opts()
    assert "extractor_args" not in opts
    assert "http_headers" not in opts
