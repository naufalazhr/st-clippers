"""The styling surface an agent can drive, and the line it must not cross.

The app can also rewrite the transcribed caption text; that is deliberately not
reachable from MCP. These tests pin both halves: the styling that must work, and
the text editing that must stay out.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

import api
import mcp_tools
from api import ClipCandidate, ClipJob, ClipJobRequest


def call(name, **args):
    return mcp_tools.dispatch("tools/call", {"name": name, "arguments": args})


def _job(job_id="job-1", status="completed", work_dir="slug", candidates=None):
    return ClipJob(
        id=job_id,
        status=status,
        request=ClipJobRequest(url="https://youtu.be/x"),
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at="now",
        work_dir=work_dir,
        candidates=candidates if candidates is not None else [
            ClipCandidate(index=1, start=10.0, end=40.0, duration=30.0,
                          score=80, title="t", reason="r", text="x")
        ],
    )


@pytest.fixture
def jobs(monkeypatch):
    store: dict[str, ClipJob] = {}
    monkeypatch.setattr(api, "jobs", store)
    return store


# --- the boundary -----------------------------------------------------------

def test_caption_text_cannot_be_edited_from_mcp():
    """The one capability held back: rewriting what was transcribed."""
    schemas = {t["name"]: t["inputSchema"]["properties"] for t in mcp_tools.TOOL_DEFINITIONS}
    for name, props in schemas.items():
        assert "segments" not in props, name
        assert "caption_text" not in props, name
        assert "transcript" not in props, name


def test_restyle_says_it_cannot_change_wording():
    tool = next(t for t in mcp_tools.TOOL_DEFINITIONS if t["name"] == "restyle_clip")
    assert "cannot change the caption wording" in tool["description"]


def test_no_tool_accepts_or_returns_a_provider_key():
    for tool in mcp_tools.TOOL_DEFINITIONS:
        assert "ai_api_key" not in tool["inputSchema"]["properties"], tool["name"]
    assert "ai_api_key" not in mcp_tools.STYLE_PROPERTIES
    assert "ai_api_key" not in mcp_tools.CREATION_PROPERTIES


# --- discovery --------------------------------------------------------------

def test_style_options_lists_allowed_values_and_defaults():
    # Without this an agent guesses a font name, and guessing costs a render.
    structured = call("get_style_options")["ok"]["structuredContent"]["options"]
    assert structured["caption_style"]["allowed"] == [
        "classic", "bold", "boxed", "highlight", "shadow"
    ]
    assert structured["caption_font"]["default"] == "DejaVu Sans"
    assert structured["crop_mode"]["default"] == "center"
    assert "allowed" in structured["transition"]


def test_style_options_covers_everything_the_tools_accept():
    options = call("get_style_options")["ok"]["structuredContent"]["options"]
    restyle = next(t for t in mcp_tools.TOOL_DEFINITIONS if t["name"] == "restyle_clip")
    for name in restyle["inputSchema"]["properties"]:
        if name in ("job_id", "clip_index", "wait_seconds"):
            continue
        assert name in options, f"{name} is settable but undocumented"


# --- styling on creation ----------------------------------------------------

def test_create_accepts_the_full_styling_surface(jobs, monkeypatch):
    captured = {}

    def fake_create(request):
        captured["r"] = request
        job = _job("new", status="running")
        jobs["new"] = job
        return job

    monkeypatch.setattr(api, "create_job", fake_create)
    reply = call(
        "create_clip_job", url="https://youtu.be/x", wait_seconds=0,
        caption_style="boxed", caption_font="Noto Sans", caption_font_size=42,
        caption_position="bottom", caption_color="#FFEE00", caption_outline=3,
        caption_outline_color="#101010", caption_box_opacity=70,
        crop_mode="split", cam_corner="br", transition="fade",
        watermark_text="@sultan", watermark_position="top-right",
        watermark_opacity=0.5, watermark_scale=120,
        top=3, min_duration=20, max_duration=60, language="id",
        required_hashtags=["#shorts"],
    )
    assert "error" not in reply, reply
    r = captured["r"]
    assert (r.caption_style, r.caption_font, r.caption_font_size) == ("boxed", "Noto Sans", 42)
    assert (r.crop_mode, r.cam_corner, r.transition) == ("split", "br", "fade")
    assert r.caption_box_opacity == 70
    assert r.watermark_text == "@sultan" and r.watermark_position == "top-right"
    assert r.top == 3 and r.required_hashtags == ["#shorts"]


def test_an_unknown_font_is_rejected_with_the_valid_ones(jobs, monkeypatch):
    monkeypatch.setattr(api, "create_job", lambda r: pytest.fail("should not start"))
    reply = call("create_clip_job", url="https://x", caption_font="Comic Sans", wait_seconds=0)
    assert reply["error"]["code"] == mcp_tools.INVALID_PARAMS
    assert "caption_font" in reply["error"]["message"]


def test_out_of_range_values_are_rejected(jobs, monkeypatch):
    monkeypatch.setattr(api, "create_job", lambda r: pytest.fail("should not start"))
    reply = call("create_clip_job", url="https://x", caption_font_size=999, wait_seconds=0)
    assert reply["error"]["code"] == mcp_tools.INVALID_PARAMS
    assert "caption_font_size" in reply["error"]["message"]


# --- restyling an existing clip --------------------------------------------

def test_restyle_reuses_the_stored_timespan(jobs, monkeypatch):
    """The agent asks to restyle a clip, not to recut a timespan it must know."""
    jobs["j"] = _job("j")
    captured = {}
    monkeypatch.setattr(api, "validate_recut", lambda *a, **k: (None, [], None))
    monkeypatch.setattr(api, "run_recut", lambda job_id, body: captured.update(body=body))

    reply = call("restyle_clip", job_id="j", clip_index=1,
                 caption_style="highlight", wait_seconds=0)
    assert "error" not in reply, reply
    import time
    for _ in range(50):
        if "body" in captured:
            break
        time.sleep(0.02)
    body = captured["body"]
    assert (body.start, body.end) == (10.0, 40.0)     # taken from the candidate
    assert body.caption_style == "highlight"
    assert body.segments is None                       # transcript left alone


def test_restyle_without_changes_does_not_render(jobs, monkeypatch):
    jobs["j"] = _job("j")
    monkeypatch.setattr(api, "run_recut", lambda *a: pytest.fail("should not render"))
    reply = call("restyle_clip", job_id="j", clip_index=1, wait_seconds=0)
    assert reply["ok"]["structuredContent"]["status"] == "no_changes"


def test_restyle_rejects_an_unknown_clip(jobs):
    jobs["j"] = _job("j")
    reply = call("restyle_clip", job_id="j", clip_index=99, caption_style="bold")
    assert reply["error"]["code"] == mcp_tools.INVALID_PARAMS
    assert "Tersedia: 1" in reply["error"]["message"]


def test_restyle_rejects_an_unknown_job(jobs):
    reply = call("restyle_clip", job_id="nope", clip_index=1, caption_style="bold")
    assert "tidak ditemukan" in reply["error"]["message"]


def test_restyle_needs_a_clip_index(jobs):
    jobs["j"] = _job("j")
    assert call("restyle_clip", job_id="j")["error"]["code"] == mcp_tools.INVALID_PARAMS


def test_restyle_is_refused_while_a_render_runs(jobs, monkeypatch):
    jobs["busy"] = _job("busy", status="running")
    jobs["j"] = _job("j")
    monkeypatch.setattr(api, "run_recut", lambda *a: pytest.fail("should not render"))
    reply = call("restyle_clip", job_id="j", clip_index=1, caption_style="bold")
    assert reply["error"]["code"] == mcp_tools.TOOL_FAILED


def test_restyle_rejects_an_invalid_style(jobs):
    jobs["j"] = _job("j")
    reply = call("restyle_clip", job_id="j", clip_index=1, caption_style="neon")
    assert reply["error"]["code"] == mcp_tools.INVALID_PARAMS


def test_restyle_reports_a_failed_render(jobs, monkeypatch):
    jobs["j"] = _job("j")
    monkeypatch.setattr(api, "validate_recut", lambda *a, **k: (None, [], None))

    def fake_recut(job_id, body):
        api.set_job(job_id, status="completed", recut_error="ffmpeg exploded")

    monkeypatch.setattr(api, "run_recut", fake_recut)
    reply = call("restyle_clip", job_id="j", clip_index=1,
                 caption_style="bold", wait_seconds=1)
    assert "ffmpeg exploded" in reply["error"]["message"]
