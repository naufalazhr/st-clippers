from __future__ import annotations

from clipper import (
    CaptionStyle,
    ClipCandidate,
    TranscriptSegment,
    build_transition_filter,
    export_clip,
)


def test_transition_none_returns_empty():
    assert build_transition_filter("none", 10.0) == ""
    # Unknown values are treated as "none".
    assert build_transition_filter("wipe", 10.0) == ""


def test_fade_has_in_and_out_stamps():
    # 10s clip: out-fade starts at 9.5 for a 0.5s fade.
    assert build_transition_filter("fade", 10.0) == (
        "fade=t=in:st=0:d=0.5,fade=t=out:st=9.500:d=0.5"
    )


def test_fadeblack_and_fadewhite_add_color_to_both_fades():
    assert build_transition_filter("fadeblack", 10.0) == (
        "fade=t=in:st=0:d=0.5:color=black,fade=t=out:st=9.500:d=0.5:color=black"
    )
    assert build_transition_filter("fadewhite", 10.0) == (
        "fade=t=in:st=0:d=0.5:color=white,fade=t=out:st=9.500:d=0.5:color=white"
    )


def test_short_clip_skips_fade_out():
    # Below the 1.2s guard only the fade-in is emitted.
    assert build_transition_filter("fade", 1.0) == "fade=t=in:st=0:d=0.5"
    # At exactly 1.2s the fade-out is kept (starts at 0.7).
    assert build_transition_filter("fade", 1.2) == (
        "fade=t=in:st=0:d=0.5,fade=t=out:st=0.700:d=0.5"
    )


def _export_with_transition(tmp_path, monkeypatch, transition: str, duration: float = 10.0):
    import clipper

    cmds: list[list[str]] = []
    monkeypatch.setattr(clipper, "run", lambda cmd, cwd=None: cmds.append(cmd))
    monkeypatch.setattr(clipper, "grab_best_frame", lambda *a, **k: None)
    monkeypatch.setattr(clipper, "generate_social_caption", lambda *a, **k: None)

    video_path = tmp_path / "source.mp4"
    clip = ClipCandidate(
        index=0, start=0.0, end=duration, duration=duration,
        score=50, title="T", reason="R", text="hi",
    )
    segments = [TranscriptSegment(start=0.0, end=2.0, text="hi")]
    out_path = export_clip(
        video_path=video_path,
        clip=clip,
        clip_segments=segments,
        clips_dir=tmp_path / "clips",
        burn_subtitles=True,
        crop_mode="center",
        caption=CaptionStyle(),
        transition=transition,
    )
    assert str(out_path).endswith(".mp4")
    # First run() call is the video pass carrying -vf.
    video_cmd = cmds[0]
    return video_cmd[video_cmd.index("-vf") + 1]


def test_export_clip_appends_fades_after_subtitles(tmp_path, monkeypatch):
    vf = _export_with_transition(tmp_path, monkeypatch, "fade")
    assert ",subtitles=" in vf
    assert vf.index("fade=t=in") > vf.index(",subtitles=")
    assert vf.endswith("fade=t=in:st=0:d=0.5,fade=t=out:st=9.500:d=0.5")


def test_export_clip_none_transition_adds_nothing(tmp_path, monkeypatch):
    vf = _export_with_transition(tmp_path, monkeypatch, "none")
    assert ",subtitles=" in vf
    assert "fade=" not in vf


def test_export_clip_fadeblack_colors_both_fades(tmp_path, monkeypatch):
    vf = _export_with_transition(tmp_path, monkeypatch, "fadeblack", duration=6.0)
    assert vf.endswith(
        "fade=t=in:st=0:d=0.5:color=black,fade=t=out:st=5.500:d=0.5:color=black"
    )
