"""Tool handlers, exercised through dispatch rather than as inner functions.

Testing the inner function passes while the dispatch path is broken -- that is
the trap the playbook calls out in Part E, so every case here goes in the way
the agent comes in.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import api
import mcp_tools
from api import ClipFile, ClipJob, ClipJobRequest


def call(name, **args):
    return mcp_tools.dispatch("tools/call", {"name": name, "arguments": args})


def _job(job_id="job-1", status="completed", clips=None, **kw):
    return ClipJob(
        id=job_id,
        status=status,
        request=ClipJobRequest(url="https://youtu.be/x", topic=kw.pop("topic", "")),
        created_at=kw.pop("created_at", datetime.now(timezone.utc).isoformat()),
        updated_at="now",
        clips=clips or [],
        **kw,
    )


@pytest.fixture
def jobs(monkeypatch):
    store: dict[str, ClipJob] = {}
    monkeypatch.setattr(api, "jobs", store)
    return store


# --- registry ---------------------------------------------------------------

def test_tools_list_shape():
    reply = mcp_tools.dispatch("tools/list", {})
    tools = reply["ok"]["tools"]
    names = {t["name"] for t in tools}
    # Every handler is advertised and every advertised tool has a handler: a
    # mismatch either hides a capability or offers one that cannot run.
    assert names == set(mcp_tools.HANDLERS)
    for tool in tools:
        assert tool["description"].strip()
        # additionalProperties: false turns a typo into an error instead of a
        # silently ignored argument.
        assert tool["inputSchema"]["additionalProperties"] is False


def test_every_inspection_tool_warns_the_agent_about_staleness():
    by_name = {t["name"]: t for t in mcp_tools.TOOL_DEFINITIONS}
    for name in ("list_jobs", "get_job", "list_clips"):
        assert "stale" in by_name[name]["description"].lower(), name


def test_unknown_tool_is_rejected():
    reply = mcp_tools.dispatch("tools/call", {"name": "drop_database", "arguments": {}})
    assert reply["error"]["code"] == mcp_tools.INVALID_PARAMS


def test_unsupported_method_is_rejected():
    assert mcp_tools.dispatch("resources/read", {})["error"]["code"] == -32601


def test_dispatch_never_raises(monkeypatch):
    monkeypatch.setattr(mcp_tools, "handle_list_jobs", lambda args: 1 / 0)
    monkeypatch.setitem(mcp_tools.HANDLERS, "list_jobs", lambda args: 1 / 0)
    reply = call("list_jobs")
    assert reply["error"]["code"] == mcp_tools.INTERNAL_ERROR


# --- listing ----------------------------------------------------------------

def test_list_jobs_when_empty(jobs):
    reply = call("list_jobs")
    assert reply["ok"]["structuredContent"]["jobs"] == []
    assert "Belum ada job" in reply["ok"]["content"][0]["text"]


def test_list_jobs_newest_first(jobs):
    older = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    jobs["a"] = _job("a", created_at=older)
    jobs["b"] = _job("b")
    listed = call("list_jobs")["ok"]["structuredContent"]["jobs"]
    assert [j["job_id"] for j in listed] == ["b", "a"]


def test_list_jobs_reports_the_topic(jobs):
    jobs["a"] = _job("a", topic="telegram bot")
    assert call("list_jobs")["ok"]["structuredContent"]["jobs"][0]["topic"] == "telegram bot"


# --- reading one job --------------------------------------------------------

def test_get_job_requires_an_id(jobs):
    assert call("get_job")["error"]["code"] == mcp_tools.INVALID_PARAMS


def test_get_job_unknown_id(jobs):
    assert "tidak ditemukan" in call("get_job", job_id="nope")["error"]["message"]


def test_get_job_reports_clips_with_scores(jobs, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    clip_file = tmp_path / "slug" / "clips" / "clip_01_a.mp4"
    clip_file.parent.mkdir(parents=True)
    clip_file.write_bytes(b"video")
    jobs["j"] = _job("j", clips=[ClipFile(
        name="clip_01_a.mp4", url="/outputs/slug/clips/clip_01_a.mp4?v=1",
        size_bytes=5, virality_score=91, virality_reason="orang bakal share",
    )])

    structured = call("get_job", job_id="j")["ok"]["structuredContent"]
    assert structured["clips"][0]["virality_score"] == 91
    # Telegram sends a local file in one call; a URL would force a download and
    # re-upload.
    assert structured["clips"][0]["path"] == str(clip_file.resolve())


def test_clip_path_is_none_when_the_file_is_gone(jobs, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    jobs["j"] = _job("j", clips=[ClipFile(
        name="gone.mp4", url="/outputs/slug/clips/gone.mp4", size_bytes=5)])
    assert call("get_job", job_id="j")["ok"]["structuredContent"]["clips"][0]["path"] is None


def test_a_path_outside_the_output_dir_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path / "outputs")
    (tmp_path / "outputs").mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("x", encoding="utf-8")
    clip = ClipFile(name="e.mp4", url="/outputs/../secret.txt", size_bytes=1)
    assert mcp_tools.clip_absolute_path(api, clip) is None


def test_list_clips_ranks_and_describes(jobs, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    jobs["j"] = _job("j", clips=[
        ClipFile(name="hi.mp4", url="/outputs/a.mp4", size_bytes=1,
                 virality_score=90, virality_reason="hook kuat"),
        ClipFile(name="lo.mp4", url="/outputs/b.mp4", size_bytes=1,
                 virality_score=40, virality_reason="biasa"),
    ])
    reply = call("list_clips", job_id="j")
    assert [c["virality_score"] for c in reply["ok"]["structuredContent"]["clips"]] == [90, 40]
    assert "hook kuat" in reply["ok"]["content"][0]["text"]


# --- creating a job ---------------------------------------------------------

def test_missing_url_is_a_result_not_an_error(jobs):
    # An agent told what is missing asks the user; one told "invalid arguments"
    # invents a value.
    reply = call("create_clip_job")
    assert "error" not in reply
    assert reply["ok"]["structuredContent"] == {"status": "needs_input", "missing": ["url"]}


def test_needs_input_leaves_nothing_behind(jobs):
    call("create_clip_job", topic="apa saja")
    assert jobs == {}  # checked before any side effect


def test_create_passes_the_topic_through(jobs, monkeypatch):
    captured = {}

    def fake_create(request):
        captured["request"] = request
        job = _job("new", status="running")
        jobs["new"] = job
        return job

    monkeypatch.setattr(api, "create_job", fake_create)
    reply = call("create_clip_job", url="https://youtu.be/x", topic="cara pakai bot",
                 wait_seconds=0)
    assert captured["request"].topic == "cara pakai bot"
    assert captured["request"].url == "https://youtu.be/x"
    assert reply["ok"]["structuredContent"]["status"] == "running"
    assert "job_id" in reply["ok"]["structuredContent"]


def test_create_forwards_optional_settings(jobs, monkeypatch):
    captured = {}
    monkeypatch.setattr(api, "create_job",
                        lambda r: (captured.setdefault("r", r), _job("n", status="running"))[1])
    call("create_clip_job", url="https://x", top=3, crop_mode="split",
         burn_subtitles=False, wait_seconds=0)
    assert captured["r"].top == 3
    assert captured["r"].crop_mode == "split"
    assert captured["r"].burn_subtitles is False


def test_bad_parameters_are_rejected_readably(jobs):
    reply = call("create_clip_job", url="https://x", top="banyak", wait_seconds=0)
    assert reply["error"]["code"] == mcp_tools.INVALID_PARAMS
    assert "top" in reply["error"]["message"]


def test_an_invalid_crop_mode_is_rejected(jobs):
    reply = call("create_clip_job", url="https://x", crop_mode="diagonal", wait_seconds=0)
    assert reply["error"]["code"] == mcp_tools.INVALID_PARAMS


# --- guardrails -------------------------------------------------------------

def test_a_second_concurrent_job_is_refused(jobs, monkeypatch):
    jobs["running"] = _job("running", status="running")
    monkeypatch.setattr(api, "create_job", lambda r: pytest.fail("should not start"))
    reply = call("create_clip_job", url="https://youtu.be/x", wait_seconds=0)
    assert reply["error"]["code"] == mcp_tools.TOOL_FAILED
    assert "sedang berjalan" in reply["error"]["message"]


def test_the_hourly_cap_is_enforced(jobs, monkeypatch):
    for i in range(mcp_tools.MAX_JOBS_PER_HOUR):
        jobs[f"j{i}"] = _job(f"j{i}", status="completed")
    monkeypatch.setattr(api, "create_job", lambda r: pytest.fail("should not start"))
    reply = call("create_clip_job", url="https://youtu.be/x", wait_seconds=0)
    assert "per jam" in reply["error"]["message"]


def test_old_jobs_do_not_count_towards_the_hourly_cap(jobs, monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    for i in range(mcp_tools.MAX_JOBS_PER_HOUR + 3):
        jobs[f"j{i}"] = _job(f"j{i}", status="completed", created_at=old)
    started = {}
    monkeypatch.setattr(api, "create_job",
                        lambda r: (started.setdefault("yes", True), _job("n", status="running"))[1])
    call("create_clip_job", url="https://youtu.be/x", wait_seconds=0)
    assert started == {"yes": True}


# --- long-poll contract -----------------------------------------------------

def test_wait_seconds_is_capped_below_the_agent_budget():
    assert mcp_tools._clamp_wait(9999) == mcp_tools.MAX_WAIT_SECONDS
    assert mcp_tools._clamp_wait(-5) == 0
    assert mcp_tools._clamp_wait("abc") == mcp_tools.DEFAULT_WAIT_SECONDS
    assert mcp_tools._clamp_wait(30) == 30


def test_still_running_returns_the_same_shape_plus_status(jobs, monkeypatch):
    jobs["j"] = _job("j", status="running")
    finished = call("get_job", job_id="j", wait_seconds=0)["ok"]["structuredContent"]
    # An agent should not need two parsers.
    assert {"job_id", "status", "clips", "clips_ready"} <= set(finished)
    assert finished["status"] == "running"


def test_waiting_returns_as_soon_as_the_job_finishes(jobs, monkeypatch):
    import threading

    jobs["j"] = _job("j", status="running")

    def finish():
        jobs["j"].status = "completed"

    threading.Timer(0.3, finish).start()
    reply = call("get_job", job_id="j", wait_seconds=10)
    assert reply["ok"]["structuredContent"]["status"] == "completed"
