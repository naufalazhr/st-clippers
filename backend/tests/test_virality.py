"""Topic steering, virality verdicts, and score-ranked results."""
from __future__ import annotations

import json

import api
import clipper
from api import ClipJobRequest, build_clipper_command, clip_verdict, discover_clips
from clipper import ClipCandidate, ai_rescore_candidates, topic_instruction


def _candidate(index=0, score=50, text="hello"):
    return ClipCandidate(index=index, start=0.0, end=10.0, duration=10.0,
                         score=score, title="t", reason="r", text=text)


def _ai():
    return clipper.AIConfig(enabled=True, base_url="http://x/v1", model="m")


# --- topic steering ---------------------------------------------------------

def test_topic_steers_the_prompt():
    out = topic_instruction("cara pakai Telegram bot")
    assert "cara pakai Telegram bot" in out
    assert "Rank candidates covering that topic" in out


def test_blank_topic_adds_nothing():
    assert topic_instruction("") == ""
    assert topic_instruction("   ") == ""


def test_topic_is_length_capped():
    assert len(topic_instruction("x" * 5000)) < 1000


def test_topic_reaches_the_pipeline_command():
    cmd = build_clipper_command(ClipJobRequest(url="https://x", topic="  automation  "))
    assert "--topic" in cmd
    assert cmd[cmd.index("--topic") + 1] == "automation"


def test_topic_is_omitted_when_not_given():
    assert "--topic" not in build_clipper_command(ClipJobRequest(url="https://x"))


def test_topic_is_sent_to_the_model(monkeypatch):
    seen = {}

    def fake_chat(config, messages):
        seen["prompt"] = messages[-1]["content"]
        return json.dumps({"clips": []})

    monkeypatch.setattr(clipper, "chat_completion", fake_chat)
    ai_rescore_candidates([_candidate()], _ai(), "monetisasi konten")
    assert "monetisasi konten" in seen["prompt"]
    assert "virality_reason" in seen["prompt"]


# --- the verdict ------------------------------------------------------------

def test_model_verdict_is_applied(monkeypatch):
    def fake_chat(config, messages):
        return json.dumps({"clips": [{"id": 0, "score": 91, "title": "Hook",
                                      "reason": "tight",
                                      "virality_reason": "people argue about it"}]})

    monkeypatch.setattr(clipper, "chat_completion", fake_chat)
    out = ai_rescore_candidates([_candidate()], _ai())
    assert out[0].virality_score == 91
    assert out[0].virality_reason == "people argue about it"


def test_verdict_falls_back_to_the_reason(monkeypatch):
    def fake_chat(config, messages):
        return json.dumps({"clips": [{"id": 0, "score": 70, "reason": "clear payoff"}]})

    monkeypatch.setattr(clipper, "chat_completion", fake_chat)
    out = ai_rescore_candidates([_candidate()], _ai())
    assert out[0].virality_score == 70
    assert out[0].virality_reason == "clear payoff"


def test_verdict_is_read_from_the_clip_sidecar(tmp_path):
    clip = tmp_path / "clip_01_a.mp4"
    clip.write_bytes(b"v")
    clip.with_suffix(".json").write_text(
        json.dumps({"virality_score": 88, "virality_reason": "surprising"}), encoding="utf-8")
    assert clip_verdict(clip) == (88, "surprising")


def test_missing_or_broken_sidecar_is_survivable(tmp_path):
    clip = tmp_path / "clip_01_a.mp4"
    clip.write_bytes(b"v")
    assert clip_verdict(clip) == (0, "")
    clip.with_suffix(".json").write_text("{not json", encoding="utf-8")
    assert clip_verdict(clip) == (0, "")


def test_old_clips_fall_back_to_the_plain_score(tmp_path):
    clip = tmp_path / "clip_01_a.mp4"
    clip.write_bytes(b"v")
    clip.with_suffix(".json").write_text(
        json.dumps({"score": 64, "reason": "solid hook"}), encoding="utf-8")
    assert clip_verdict(clip) == (64, "solid hook")


# --- ranking ----------------------------------------------------------------

def test_clips_are_ranked_by_virality(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    d = tmp_path / "clips"
    d.mkdir(parents=True)
    for name, score in [("clip_01_a.mp4", 40), ("clip_02_b.mp4", 95), ("clip_03_c.mp4", 70)]:
        f = d / name
        f.write_bytes(b"v")
        f.with_suffix(".json").write_text(json.dumps({"virality_score": score}), encoding="utf-8")

    ranked = discover_clips(0)
    assert [c.name for c in ranked] == ["clip_02_b.mp4", "clip_03_c.mp4", "clip_01_a.mp4"]
    assert [c.virality_score for c in ranked] == [95, 70, 40]


def test_ties_keep_a_stable_order(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    d = tmp_path / "clips"
    d.mkdir(parents=True)
    for name in ("clip_02_b.mp4", "clip_01_a.mp4"):
        f = d / name
        f.write_bytes(b"v")
        f.with_suffix(".json").write_text(json.dumps({"virality_score": 50}), encoding="utf-8")
    assert [c.name for c in discover_clips(0)] == ["clip_01_a.mp4", "clip_02_b.mp4"]
