"""Recut: cache-busted URLs and background rendering."""
from __future__ import annotations

import os
import time

import pytest

import api
from api import ClipJob, ClipJobRequest, clip_url, jobs, jobs_lock


def _make_clip(tmp_path, name="clip_00_x.mp4"):
    d = tmp_path / "clips"
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_bytes(b"video")
    return f


def test_clip_url_is_versioned_by_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    f = _make_clip(tmp_path)
    first = clip_url(f)
    assert "?v=" in first

    # A recut rewrites the same path; the URL must change or the webview keeps
    # serving the copy it cached (edit appeared to do nothing, and seeking a
    # stale copy stalled at the end).
    later = time.time() + 50
    os.utime(f, (later, later))
    assert clip_url(f) != first


def test_clip_url_keeps_the_path_intact(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    f = _make_clip(tmp_path, "clip_01_a b.mp4")
    url = clip_url(f)
    assert url.startswith("/outputs/clips/")
    assert url.split("?")[0].endswith("clip_01_a%20b.mp4")


def test_clip_url_survives_a_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    missing = tmp_path / "clips" / "gone.mp4"
    missing.parent.mkdir(parents=True, exist_ok=True)
    assert clip_url(missing) == "/outputs/clips/gone.mp4"


@pytest.fixture
def completed_job():
    from api import ClipCandidate

    job_id = "recut-job"
    with jobs_lock:
        jobs.clear()
        jobs[job_id] = ClipJob(
            id=job_id,
            status="completed",
            request=ClipJobRequest(url="https://youtu.be/x"),
            created_at="now",
            updated_at="now",
            work_dir="slug",
            candidates=[
                ClipCandidate(index=0, start=0.0, end=10.0, duration=10.0,
                              score=1, title="t", reason="r", text="x")
            ],
        )
    yield job_id
    with jobs_lock:
        jobs.clear()


def test_recut_returns_immediately_and_marks_the_job_running(completed_job, monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, target, args, daemon=None):
            started.append(args)

        def start(self):
            pass

    monkeypatch.setattr(api.threading, "Thread", FakeThread)
    # This job has no real work dir; validation is covered by its own tests.
    monkeypatch.setattr(api, "validate_recut", lambda *a, **k: (None, [], None))
    from fastapi.testclient import TestClient

    client = TestClient(api.app)
    r = client.post(
        f"/api/jobs/{completed_job}/recut",
        json={"index": 0, "start": 0.0, "end": 10.0},
    )
    assert r.status_code == 200, r.json()
    assert r.json() == {"status": "started", "index": 0}
    assert started, "render was not handed to a background thread"

    with jobs_lock:
        job = jobs[completed_job]
    assert job.status == "running"
    assert job.recut_index == 0
    assert job.recut_error is None


def test_recut_rejects_an_unknown_clip(completed_job, monkeypatch):
    # Validation runs in the request, so a bad index still fails with 400
    # rather than surfacing later through recut_error.
    def reject(job, index, start, end, segments=None):
        raise ValueError("candidate not found")

    monkeypatch.setattr(api, "validate_recut", reject)
    from fastapi.testclient import TestClient

    r = TestClient(api.app).post(
        f"/api/jobs/{completed_job}/recut",
        json={"index": 99, "start": 0.0, "end": 10.0},
    )
    assert r.status_code == 400


def test_recut_refuses_while_the_job_is_already_rendering(completed_job):
    from fastapi.testclient import TestClient

    api.set_job(completed_job, status="running")
    r = TestClient(api.app).post(
        f"/api/jobs/{completed_job}/recut",
        json={"index": 0, "start": 0.0, "end": 10.0},
    )
    assert r.status_code == 409


def test_failed_recut_keeps_the_job_completed_and_reports(completed_job, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ffmpeg exploded")

    monkeypatch.setattr(api, "recut_clip", boom)
    api.run_recut(completed_job, api.RecutRequest(index=0, start=0.0, end=10.0))

    with jobs_lock:
        job = jobs[completed_job]
    # The job's existing clips are still valid -- only the re-render failed.
    assert job.status == "completed"
    assert job.recut_index is None
    assert "ffmpeg exploded" in (job.recut_error or "")


def test_successful_recut_clears_progress_state(completed_job, monkeypatch):
    from api import ClipCandidate, ClipFile

    new_clip = ClipFile(name="clip_00_x.mp4", url="/outputs/x.mp4?v=2", size_bytes=10)
    new_cand = ClipCandidate(index=0, start=0.0, end=9.0, duration=9.0,
                             score=2, title="new", reason="r", text="x")
    monkeypatch.setattr(api, "recut_clip", lambda *a, **k: (new_clip, new_cand))

    api.run_recut(completed_job, api.RecutRequest(index=0, start=0.0, end=9.0))

    with jobs_lock:
        job = jobs[completed_job]
    assert job.status == "completed"
    assert job.recut_index is None
    assert job.recut_error is None
    assert job.candidates[0].title == "new"
