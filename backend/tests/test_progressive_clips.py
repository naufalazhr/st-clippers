"""Clips must reach the UI as they finish, not only when the job ends."""
from __future__ import annotations

import time

import api
from api import INCOMPLETE_CLIP_SUFFIX, discover_clips


def _clip(dirpath, name, mtime=None):
    d = dirpath / "clips"
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_bytes(b"\x00" * 1024)
    if mtime:
        import os

        os.utime(f, (mtime, mtime))
    return f


def test_half_written_clips_are_hidden(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    started = time.time() - 10
    _clip(tmp_path, "clip_01_done.mp4")
    _clip(tmp_path, "clip_02_wip" + INCOMPLETE_CLIP_SUFFIX)

    names = [c.name for c in discover_clips(started)]
    assert names == ["clip_01_done.mp4"]


def test_clips_finished_before_the_job_started_are_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    started = time.time()
    _clip(tmp_path, "old.mp4", mtime=started - 3600)
    _clip(tmp_path, "new.mp4")

    assert [c.name for c in discover_clips(started - 1)] == ["new.mp4"]


def test_clips_accumulate_in_order_as_they_land(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    started = time.time() - 10

    _clip(tmp_path, "clip_02_b.mp4")
    assert [c.name for c in discover_clips(started)] == ["clip_02_b.mp4"]

    _clip(tmp_path, "clip_01_a.mp4")
    # Sorted by name so the list stays stable while the UI is watching it.
    assert [c.name for c in discover_clips(started)] == ["clip_01_a.mp4", "clip_02_b.mp4"]


def test_job_model_carries_the_expected_clip_count():
    job = api.ClipJob(
        id="x",
        status="running",
        request=api.ClipJobRequest(url="https://x"),
        created_at="now",
        updated_at="now",
        clips_expected=4,
    )
    assert job.clips_expected == 4
    # Optional, so existing persisted jobs keep loading.
    assert api.ClipJob(
        id="y",
        status="queued",
        request=api.ClipJobRequest(url="https://x"),
        created_at="now",
        updated_at="now",
    ).clips_expected is None


def test_run_job_publishes_clips_before_the_process_exits():
    # The scan runs inside the stdout loop, not after process.wait().
    source = (__import__("pathlib").Path(api.__file__)).read_text(encoding="utf-8")
    loop = source.index("for line in process.stdout:")
    wait = source.index("code = process.wait()")
    scan = source.index("set_job(job_id, clips=ready)")
    assert loop < scan < wait
