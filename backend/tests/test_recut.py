from __future__ import annotations

import unittest.mock
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from api import app, ClipJob, ClipJobRequest, ClipCandidate, ClipFile, jobs, jobs_lock


class _InlineThread:
    """Run a background target synchronously so tests stay deterministic.

    The recut endpoint hands the render to a thread; these tests care about what
    it does, not that it is concurrent.
    """

    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


@pytest.fixture(autouse=True)
def clear_jobs():
    with jobs_lock:
        jobs.clear()
    yield


def test_recut_rejects_bad_bounds():
    with jobs_lock:
        jobs["test"] = ClipJob(
            id="test",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            candidates=[ClipCandidate(index=0, start=0, end=10, duration=10, score=50, title="t", reason="r", text="hello")],
            work_dir="some-slug",
        )
    client = TestClient(app)
    resp = client.post("/api/jobs/test/recut", json={"index": 0, "start": 10, "end": 5})
    assert resp.status_code == 400


def test_recut_candidate_rebuild():
    with jobs_lock:
        jobs["test2"] = ClipJob(
            id="test2",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x", crop_mode="center"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            candidates=[ClipCandidate(index=0, start=0, end=10, duration=10, score=50, title="My Title", reason="good", text="hello world")],
            work_dir="some-slug",
        )

    py_cand = ClipCandidate(index=0, start=0, end=5, duration=5, score=50, title="My Title", reason="good", text="hello world")
    py_clip = ClipFile(name="clip_00_test.mp4", url="/outputs/x", size_bytes=100)

    with unittest.mock.patch("api.recut_clip", return_value=(py_clip, py_cand)),          unittest.mock.patch("api.validate_recut", return_value=(None, [], py_cand)),          unittest.mock.patch("api.threading.Thread", _InlineThread):
        client = TestClient(app)
        resp = client.post("/api/jobs/test2/recut", json={"index": 0, "start": 0, "end": 5})

    assert resp.status_code == 200
    assert resp.json() == {"status": "started", "index": 0}

    # The rebuilt candidate is applied to the job by the background render.
    with jobs_lock:
        cand = jobs["test2"].candidates[0]
    assert cand.start == 0
    assert cand.end == 5
    assert cand.duration == 5
    assert cand.score == 50
    assert cand.title == "My Title"


def test_recut_endpoint_404_unknown_job():
    client = TestClient(app)
    resp = client.post("/api/jobs/nonexistent/recut", json={"index": 0, "start": 0, "end": 5})
    assert resp.status_code == 404


def test_recut_endpoint_404_no_source():
    with jobs_lock:
        jobs["test3"] = ClipJob(
            id="test3",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            work_dir=None,
        )
    client = TestClient(app)
    resp = client.post("/api/jobs/test3/recut", json={"index": 0, "start": 0, "end": 5})
    assert resp.status_code == 404


def test_recut_with_segments_passes_correct_clip_segments(tmp_path):
    """Given override segments, recut_clip must call export_clip with those segments."""
    from clipper import TranscriptSegment as TranscriptSegmentDC
    import json as _json

    work_dir = tmp_path / "fake-slug"
    (work_dir / "clips").mkdir(parents=True)
    source = work_dir / "source.mp4"
    source.write_bytes(b"fake")
    transcript = [{"start": 0.0, "end": 5.0, "text": "original text"}]
    (work_dir / "transcript.json").write_text(_json.dumps(transcript), encoding="utf-8")

    with jobs_lock:
        jobs["seg_test"] = ClipJob(
            id="seg_test",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            candidates=[ClipCandidate(index=0, start=0, end=10, duration=10, score=80, title="T", reason="R", text="original text")],
            work_dir=None,
        )

    override_segs = [{"start": 1.0, "end": 4.0, "text": "corrected text"}]
    captured: dict = {}

    def fake_export_clip(**kwargs):
        captured["clip_segments"] = kwargs["clip_segments"]
        out = tmp_path / "fake-slug" / "clips" / "clip_00_test.mp4"
        out.write_bytes(b"fake")
        return out

    def fake_probe(path):
        return 20.0

    import api as api_module
    real_outputs_dir = api_module.OUTPUTS_DIR
    try:
        api_module.OUTPUTS_DIR = tmp_path
        jobs["seg_test"].work_dir = "fake-slug"
        with (
            unittest.mock.patch("clipper.export_clip", side_effect=fake_export_clip),
            unittest.mock.patch("api.probe_media_duration", side_effect=fake_probe),
        ):
            from api import recut_clip
            _, _ = recut_clip(jobs["seg_test"], 0, 0.0, 10.0, override_segs)
    finally:
        api_module.OUTPUTS_DIR = real_outputs_dir

    assert len(captured["clip_segments"]) == 1
    assert captured["clip_segments"][0].text == "corrected text"
    edited = (tmp_path / "fake-slug" / "transcript_edited.json")
    assert edited.exists()
    assert _json.loads(edited.read_text(encoding="utf-8")) == override_segs


def test_recut_empty_segments_returns_400(tmp_path):
    import json as _json

    work_dir = tmp_path / "empty-slug"
    (work_dir / "clips").mkdir(parents=True)
    source = work_dir / "source.mp4"
    source.write_bytes(b"fake")
    transcript = [{"start": 0.0, "end": 5.0, "text": "hello"}]
    (work_dir / "transcript.json").write_text(_json.dumps(transcript), encoding="utf-8")

    with jobs_lock:
        jobs["empty_seg"] = ClipJob(
            id="empty_seg",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            candidates=[ClipCandidate(index=0, start=0, end=10, duration=10, score=50, title="T", reason="R", text="hello")],
            work_dir="empty-slug",
        )

    import api as api_module
    real_outputs_dir = api_module.OUTPUTS_DIR
    try:
        api_module.OUTPUTS_DIR = tmp_path
        client = TestClient(app)
        resp = client.post(
            "/api/jobs/empty_seg/recut",
            json={"index": 0, "start": 0.0, "end": 10.0, "segments": []},
        )
    finally:
        api_module.OUTPUTS_DIR = real_outputs_dir

    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_recut_without_segments_regression():
    py_cand = ClipCandidate(index=0, start=2, end=8, duration=6, score=60, title="T", reason="R", text="hello")
    py_clip = ClipFile(name="clip_00_x.mp4", url="/outputs/x", size_bytes=200)

    with jobs_lock:
        jobs["compat_test"] = ClipJob(
            id="compat_test",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            candidates=[ClipCandidate(index=0, start=0, end=10, duration=10, score=60, title="T", reason="R", text="hello")],
            work_dir="some-slug",
        )

    with unittest.mock.patch("api.recut_clip", return_value=(py_clip, py_cand)) as mock_recut,          unittest.mock.patch("api.validate_recut", return_value=(None, [], py_cand)),          unittest.mock.patch("api.threading.Thread", _InlineThread):
        client = TestClient(app)
        resp = client.post("/api/jobs/compat_test/recut", json={"index": 0, "start": 2, "end": 8})

    assert resp.status_code == 200
    _, kwargs = mock_recut.call_args
    assert kwargs.get("override_segments") is None or mock_recut.call_args[0][4] is None


def test_recut_caption_override_used(tmp_path):
    import json as _json

    work_dir = tmp_path / "cap-slug"
    (work_dir / "clips").mkdir(parents=True)
    (work_dir / "source.mp4").write_bytes(b"fake")
    (work_dir / "transcript.json").write_text(
        _json.dumps([{"start": 0.0, "end": 5.0, "text": "hi"}]), encoding="utf-8"
    )

    with jobs_lock:
        jobs["cap_test"] = ClipJob(
            id="cap_test",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x", caption_font_size=30, caption_color="#FFFFFF"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            candidates=[ClipCandidate(index=0, start=0, end=10, duration=10, score=50, title="T", reason="R", text="hi")],
            work_dir="cap-slug",
        )

    captured: dict = {}

    def fake_export(**kwargs):
        captured["caption"] = kwargs["caption"]
        out = tmp_path / "cap-slug" / "clips" / "clip_00_t.mp4"
        out.write_bytes(b"fake")
        return out

    import api as api_module
    real_outputs_dir = api_module.OUTPUTS_DIR
    try:
        api_module.OUTPUTS_DIR = tmp_path
        with (
            unittest.mock.patch("clipper.export_clip", side_effect=fake_export),
            unittest.mock.patch("api.probe_media_duration", return_value=20.0),
        ):
            from api import recut_clip, RecutRequest
            rr = RecutRequest(index=0, start=0, end=10, caption_font_size=72, caption_color="#FF0000")
            recut_clip(jobs["cap_test"], 0, 0.0, 10.0, None, rr)
    finally:
        api_module.OUTPUTS_DIR = real_outputs_dir

    assert captured["caption"].font_size == 72
    assert captured["caption"].color == "#FF0000"


def test_recut_caption_falls_back_to_job_request(tmp_path):
    import json as _json

    work_dir = tmp_path / "fb-slug"
    (work_dir / "clips").mkdir(parents=True)
    (work_dir / "source.mp4").write_bytes(b"fake")
    (work_dir / "transcript.json").write_text(
        _json.dumps([{"start": 0.0, "end": 5.0, "text": "hi"}]), encoding="utf-8"
    )

    with jobs_lock:
        jobs["fb_test"] = ClipJob(
            id="fb_test",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x", caption_font_size=55),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            candidates=[ClipCandidate(index=0, start=0, end=10, duration=10, score=50, title="T", reason="R", text="hi")],
            work_dir="fb-slug",
        )

    captured: dict = {}

    def fake_export(**kwargs):
        captured["caption"] = kwargs["caption"]
        out = tmp_path / "fb-slug" / "clips" / "clip_00_t.mp4"
        out.write_bytes(b"fake")
        return out

    import api as api_module
    real_outputs_dir = api_module.OUTPUTS_DIR
    try:
        api_module.OUTPUTS_DIR = tmp_path
        with (
            unittest.mock.patch("clipper.export_clip", side_effect=fake_export),
            unittest.mock.patch("api.probe_media_duration", return_value=20.0),
        ):
            from api import recut_clip, RecutRequest
            rr = RecutRequest(index=0, start=0, end=10)
            recut_clip(jobs["fb_test"], 0, 0.0, 10.0, None, rr)
    finally:
        api_module.OUTPUTS_DIR = real_outputs_dir

    assert captured["caption"].font_size == 55


def test_recut_style_and_transition_overrides(tmp_path):
    import json as _json

    work_dir = tmp_path / "style-slug"
    (work_dir / "clips").mkdir(parents=True)
    (work_dir / "source.mp4").write_bytes(b"fake")
    (work_dir / "transcript.json").write_text(
        _json.dumps([{"start": 0.0, "end": 5.0, "text": "hi"}]), encoding="utf-8"
    )

    with jobs_lock:
        jobs["style_test"] = ClipJob(
            id="style_test",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x", caption_style="classic", transition="none"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            candidates=[ClipCandidate(index=0, start=0, end=10, duration=10, score=50, title="T", reason="R", text="hi")],
            work_dir="style-slug",
        )

    captured: dict = {}

    def fake_export(**kwargs):
        captured["caption"] = kwargs["caption"]
        captured["transition"] = kwargs["transition"]
        out = tmp_path / "style-slug" / "clips" / "clip_00_t.mp4"
        out.write_bytes(b"fake")
        return out

    import api as api_module
    real_outputs_dir = api_module.OUTPUTS_DIR
    try:
        api_module.OUTPUTS_DIR = tmp_path
        with (
            unittest.mock.patch("clipper.export_clip", side_effect=fake_export),
            unittest.mock.patch("api.probe_media_duration", return_value=20.0),
        ):
            from api import recut_clip, RecutRequest
            rr = RecutRequest(index=0, start=0, end=10, caption_style="boxed", transition="fade")
            recut_clip(jobs["style_test"], 0, 0.0, 10.0, None, rr)
    finally:
        api_module.OUTPUTS_DIR = real_outputs_dir

    assert captured["caption"].style == "boxed"
    assert captured["transition"] == "fade"


def test_recut_style_and_transition_fall_back_to_job_request(tmp_path):
    import json as _json

    work_dir = tmp_path / "fallback-slug"
    (work_dir / "clips").mkdir(parents=True)
    (work_dir / "source.mp4").write_bytes(b"fake")
    (work_dir / "transcript.json").write_text(
        _json.dumps([{"start": 0.0, "end": 5.0, "text": "hi"}]), encoding="utf-8"
    )

    with jobs_lock:
        jobs["fallback_test"] = ClipJob(
            id="fallback_test",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x", caption_style="shadow", transition="fadeblack"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            candidates=[ClipCandidate(index=0, start=0, end=10, duration=10, score=50, title="T", reason="R", text="hi")],
            work_dir="fallback-slug",
        )

    captured: dict = {}

    def fake_export(**kwargs):
        captured["caption"] = kwargs["caption"]
        captured["transition"] = kwargs["transition"]
        out = tmp_path / "fallback-slug" / "clips" / "clip_00_t.mp4"
        out.write_bytes(b"fake")
        return out

    import api as api_module
    real_outputs_dir = api_module.OUTPUTS_DIR
    try:
        api_module.OUTPUTS_DIR = tmp_path
        with (
            unittest.mock.patch("clipper.export_clip", side_effect=fake_export),
            unittest.mock.patch("api.probe_media_duration", return_value=20.0),
        ):
            from api import recut_clip, RecutRequest
            rr = RecutRequest(index=0, start=0, end=10)
            recut_clip(jobs["fallback_test"], 0, 0.0, 10.0, None, rr)
    finally:
        api_module.OUTPUTS_DIR = real_outputs_dir

    assert captured["caption"].style == "shadow"
    assert captured["transition"] == "fadeblack"


def test_recut_rejects_unknown_caption_style():
    client = TestClient(app)
    resp = client.post(
        "/api/jobs/nope/recut",
        json={"index": 0, "start": 0, "end": 5, "caption_style": "neon"},
    )
    assert resp.status_code == 422


def test_recut_rejects_unknown_transition():
    client = TestClient(app)
    resp = client.post(
        "/api/jobs/nope/recut",
        json={"index": 0, "start": 0, "end": 5, "transition": "wipe"},
    )
    assert resp.status_code == 422


def test_job_request_validates_caption_style_and_transition():
    from pydantic import ValidationError

    req = ClipJobRequest(url="https://youtu.be/x", caption_style="highlight", transition="fadewhite")
    assert req.caption_style == "highlight"
    assert req.transition == "fadewhite"
    # Defaults.
    plain = ClipJobRequest(url="https://youtu.be/x")
    assert plain.caption_style == "classic"
    assert plain.transition == "none"
    with pytest.raises(ValidationError):
        ClipJobRequest(url="https://youtu.be/x", caption_style="neon")
    with pytest.raises(ValidationError):
        ClipJobRequest(url="https://youtu.be/x", transition="slide")


def test_recut_watermark_passed_to_export(tmp_path):
    import json as _json

    work_dir = tmp_path / "wm-slug"
    (work_dir / "clips").mkdir(parents=True)
    (work_dir / "source.mp4").write_bytes(b"fake")
    (work_dir / "transcript.json").write_text(
        _json.dumps([{"start": 0.0, "end": 5.0, "text": "hi"}]), encoding="utf-8"
    )

    with jobs_lock:
        jobs["wm_test"] = ClipJob(
            id="wm_test",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            candidates=[ClipCandidate(index=0, start=0, end=10, duration=10, score=50, title="T", reason="R", text="hi")],
            work_dir="wm-slug",
        )

    captured: dict = {}

    def fake_export(**kwargs):
        captured["watermark"] = kwargs.get("watermark")
        out = tmp_path / "wm-slug" / "clips" / "clip_00_t.mp4"
        out.write_bytes(b"fake")
        return out

    import api as api_module
    real_outputs_dir = api_module.OUTPUTS_DIR
    try:
        api_module.OUTPUTS_DIR = tmp_path
        with (
            unittest.mock.patch("clipper.export_clip", side_effect=fake_export),
            unittest.mock.patch("api.probe_media_duration", return_value=20.0),
        ):
            from api import recut_clip, RecutRequest
            rr = RecutRequest(index=0, start=0, end=10, watermark_text="Sultan Tech")
            recut_clip(jobs["wm_test"], 0, 0.0, 10.0, None, rr)
    finally:
        api_module.OUTPUTS_DIR = real_outputs_dir

    assert captured["watermark"] is not None
    assert captured["watermark"].text == "Sultan Tech"


def test_watermark_upload_endpoint(tmp_path):
    import io

    work_dir = tmp_path / "upload-slug"
    work_dir.mkdir(parents=True)

    with jobs_lock:
        jobs["upload_wm"] = ClipJob(
            id="upload_wm",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            work_dir="upload-slug",
        )

    import api as api_module
    real_outputs_dir = api_module.OUTPUTS_DIR
    try:
        api_module.OUTPUTS_DIR = tmp_path
        client = TestClient(app)
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        resp = client.post(
            "/api/jobs/upload_wm/watermark-upload",
            files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
        )
    finally:
        api_module.OUTPUTS_DIR = real_outputs_dir

    assert resp.status_code == 200
    assert resp.json() == {"watermark_image": "watermark.png"}
    assert (tmp_path / "upload-slug" / "watermark.png").exists()


def test_watermark_upload_rejects_non_png(tmp_path):
    import io

    work_dir = tmp_path / "badext-slug"
    work_dir.mkdir(parents=True)

    with jobs_lock:
        jobs["bad_wm"] = ClipJob(
            id="bad_wm",
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            work_dir="badext-slug",
        )

    import api as api_module
    real_outputs_dir = api_module.OUTPUTS_DIR
    try:
        api_module.OUTPUTS_DIR = tmp_path
        client = TestClient(app)
        resp = client.post(
            "/api/jobs/bad_wm/watermark-upload",
            files={"file": ("logo.jpg", io.BytesIO(b"fake"), "image/jpeg")},
        )
    finally:
        api_module.OUTPUTS_DIR = real_outputs_dir

    assert resp.status_code == 422
