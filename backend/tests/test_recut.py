from __future__ import annotations

import unittest.mock
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from api import app, ClipJob, ClipJobRequest, ClipCandidate, ClipFile, jobs, jobs_lock


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

    with unittest.mock.patch("api.recut_clip", return_value=(py_clip, py_cand)):
        client = TestClient(app)
        resp = client.post("/api/jobs/test2/recut", json={"index": 0, "start": 0, "end": 5})

    assert resp.status_code == 200
    data = resp.json()
    assert data["candidate"]["start"] == 0
    assert data["candidate"]["end"] == 5
    assert data["candidate"]["duration"] == 5
    assert data["candidate"]["score"] == 50
    assert data["candidate"]["title"] == "My Title"


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
