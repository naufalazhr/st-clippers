"""Following a subject through a clip that cuts between cameras.

A single crop position cannot serve a multi-camera edit: the speaker sits
somewhere different in each angle, so a position chosen for one shot puts them
off-frame in the others. The crop therefore moves -- but only at the instants
the source itself cuts, where the change is invisible.

Getting those instants from face positions does not work. Sampling faces every
few seconds places a boundary up to one interval after the real cut, which
leaves the outgoing camera's framing over the opening of the new shot. On the
podcast this was reported against, that put the crop on the empty backdrop
between two people for over a second. So cuts come from comparing frames, and
faces only decide where to look within each shot.
"""
from __future__ import annotations

import subprocess

import pytest

import clipper
from clipper import (
    MIN_FOCUS_SHIFT,
    MIN_SEGMENT_SECONDS,
    crop_x_expression,
    detect_scene_cuts,
    merge_focus_segments,
    shot_boundaries,
)


# --- turning cuts into shots ------------------------------------------------

def test_a_clip_with_no_cuts_is_one_shot():
    assert shot_boundaries([], 46.0) == [(0.0, 46.0)]


def test_each_cut_starts_a_shot():
    assert shot_boundaries([7.5, 15.3], 60.6) == [(0.0, 7.5), (7.5, 15.3), (15.3, 60.6)]


def test_shots_cover_the_clip_without_gaps():
    shots = shot_boundaries([7.52, 9.4, 11.48, 15.28, 58.92], 60.6)
    assert shots[0][0] == 0.0
    assert shots[-1][1] == 60.6
    for earlier, later in zip(shots, shots[1:]):
        assert earlier[1] == later[0]


def test_a_flash_between_cuts_is_folded_into_the_shot_before_it():
    # Two cuts a few frames apart are a flash or a whip pan, not a shot worth
    # moving the crop for.
    shots = shot_boundaries([10.0, 10.2], 30.0)
    assert shots == [(0.0, 10.2), (10.2, 30.0)]


def test_a_flash_at_the_very_start_joins_the_shot_after_it():
    # There is no earlier shot to fold into, so it must borrow the next one's
    # framing rather than become a segment of its own.
    shots = shot_boundaries([0.3], 30.0)
    assert shots == [(0.0, 30.0)]


def test_a_rapid_cut_sequence_does_not_shatter_the_clip():
    cuts = [round(0.4 * n, 2) for n in range(1, 25)]
    shots = shot_boundaries(cuts, 30.0)
    assert len(shots) <= 3
    assert all(end - start >= MIN_SEGMENT_SECONDS for start, end in shots)


def test_cuts_outside_the_clip_cannot_produce_a_backwards_shot():
    for start, end in shot_boundaries([0.0, 30.0, 45.0], 30.0):
        assert end > start


# --- deciding when a move is worth making -----------------------------------

def test_neighbours_at_the_same_focus_become_one_segment():
    merged = merge_focus_segments([(0.0, 5.0, 0.55), (5.0, 12.0, 0.56)])
    assert merged == [(0.0, 12.0, 0.55)]


def test_a_real_change_of_framing_is_kept():
    merged = merge_focus_segments([(0.0, 7.5, 0.59), (7.5, 15.0, 0.35)])
    assert len(merged) == 2


def test_drifting_back_does_not_accumulate_into_a_jump():
    # Each step is under the threshold; comparing against the kept focus rather
    # than the previous input stops them adding up into a visible slide.
    merged = merge_focus_segments(
        [(0.0, 3.0, 0.50), (3.0, 6.0, 0.57), (6.0, 9.0, 0.64), (9.0, 12.0, 0.71)]
    )
    assert len(merged) < 4


def test_merging_keeps_the_clip_covered():
    merged = merge_focus_segments([(0.0, 5.0, 0.5), (5.0, 9.0, 0.51), (9.0, 20.0, 0.2)])
    assert merged[0][0] == 0.0
    assert merged[-1][1] == 20.0


def test_the_shift_threshold_is_smaller_than_a_camera_change():
    # 0.09 of frame width is a nudge; the angle changes this fix exists for move
    # the subject by 0.2 and more.
    assert 0 < MIN_FOCUS_SHIFT < 0.2


# --- reading cuts out of ffmpeg ---------------------------------------------

class _Result:
    def __init__(self, stderr):
        self.stderr = stderr
        self.stdout = ""
        self.returncode = 0


@pytest.fixture
def stub_ffmpeg(monkeypatch):
    """Pin the binary so patching subprocess.run cannot break locating it."""
    monkeypatch.setattr(clipper, "ffmpeg_path", lambda: "ffmpeg")


SHOWINFO = (
    "[Parsed_showinfo_2 @ 0x1] n:0 pts:180 pts_time:7.52 pos:1 fmt:yuv420p\n"
    "[Parsed_showinfo_2 @ 0x1] n:1 pts:225 pts_time:15.28 pos:2 fmt:yuv420p\n"
)


def test_cut_times_are_read_from_ffmpeg(stub_ffmpeg, monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Result(SHOWINFO))
    assert detect_scene_cuts(tmp_path / "v.mp4", 174.76, 60.6) == [7.52, 15.28]


def test_cut_times_are_relative_to_the_clip_not_the_source(stub_ffmpeg, monkeypatch, tmp_path):
    # ffmpeg seeks before it opens the input, so its timestamps restart at zero.
    # Treating them as source times would place every cut off the end.
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return _Result(SHOWINFO)

    monkeypatch.setattr(subprocess, "run", fake_run)
    cuts = detect_scene_cuts(tmp_path / "v.mp4", 174.76, 60.6)
    assert all(0 < cut < 60.6 for cut in cuts)
    index = seen["command"].index("-ss")
    assert seen["command"].index("-i") > index, "-ss must precede -i to seek fast"


def test_timestamps_beyond_the_clip_are_ignored(stub_ffmpeg, monkeypatch, tmp_path):
    noise = SHOWINFO + "[Parsed_showinfo_2 @ 0x1] n:2 pts:9 pts_time:99.00 fmt:yuv420p\n"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Result(noise))
    assert detect_scene_cuts(tmp_path / "v.mp4", 0.0, 60.6) == [7.52, 15.28]


def test_a_failed_scan_falls_back_to_one_shot(stub_ffmpeg, monkeypatch, tmp_path):
    # Detection is an optimisation. If ffmpeg is missing or hangs, the render
    # carries on with the single static crop it used to produce.
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired("ffmpeg", 120)

    monkeypatch.setattr(subprocess, "run", boom)
    assert detect_scene_cuts(tmp_path / "v.mp4", 0.0, 60.6) == []
    assert shot_boundaries([], 60.6) == [(0.0, 60.6)]


def test_the_scan_is_bounded_and_cheap(stub_ffmpeg, monkeypatch, tmp_path):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["timeout"] = kwargs.get("timeout")
        return _Result("")

    monkeypatch.setattr(subprocess, "run", fake_run)
    detect_scene_cuts(tmp_path / "v.mp4", 0.0, 60.6)
    assert seen["timeout"] == clipper.SCENE_DETECT_TIMEOUT_SECONDS
    graph = seen["command"][seen["command"].index("-filter:v") + 1]
    # Only the size of the change matters, so it runs on a downscaled copy.
    assert graph.startswith("scale=320:")
    assert f"gt(scene,{clipper.SCENE_CUT_THRESHOLD})" in graph


# --- the ffmpeg crop expression ---------------------------------------------

def test_a_single_shot_needs_no_expression():
    assert crop_x_expression([(0.0, 10.0, 0.5)], 3414) == "1166"


def test_the_expression_switches_at_each_cut():
    expression = crop_x_expression([(0.0, 9.0, 0.60), (9.0, 20.0, 0.35)], 3414)
    assert expression == "if(lt(t,9.00),1508,654)"


def test_the_expression_nests_for_several_cuts():
    segments = [(0.0, 5.0, 0.6), (5.0, 9.0, 0.3), (9.0, 20.0, 0.5)]
    expression = crop_x_expression(segments, 3414)
    assert expression.count("if(") == 2
    assert expression.startswith("if(lt(t,5.00)")


def test_the_expression_never_leaves_the_frame():
    for focus in (0.0, 0.01, 0.5, 0.99, 1.0):
        value = int(crop_x_expression([(0.0, 5.0, focus)], 3414))
        assert 0 <= value <= 3414 - 1080


def test_ffmpeg_accepts_the_expression(tmp_path):
    """The expression is built as a string, so only ffmpeg can confirm it parses."""
    segments = [(0.0, 2.0, 0.25), (2.0, 4.0, 0.75), (4.0, 6.0, 0.4)]
    graph = f"crop=320:240:'{crop_x_expression(segments, 1280)}':0"
    result = subprocess.run(
        [clipper.ffmpeg_path(), "-hide_banner", "-nostats", "-f", "lavfi",
         "-i", "testsrc=size=1280x720:rate=10:duration=1", "-vf", graph,
         "-frames:v", "3", "-f", "null", "-"],
        capture_output=True, text=True, errors="replace",
    )
    assert result.returncode == 0, result.stderr[-1500:]


# --- the whole pipeline on one clip -----------------------------------------

def _fake_capture(width=1920, height=1080):
    import cv2
    import numpy as np

    class Capture:
        def isOpened(self):
            return True

        def set(self, *args):
            return True

        def read(self):
            return True, np.zeros((height, width, 3), dtype=np.uint8)

        def release(self):
            return None

    return Capture()


def test_a_clip_whose_shots_have_no_faces_falls_back_to_centre(monkeypatch, tmp_path):
    cv2 = pytest.importorskip("cv2")
    video = tmp_path / "v.mp4"
    video.touch()
    monkeypatch.setattr(clipper, "get_video_size", lambda p: (1920, 1080))
    monkeypatch.setattr(cv2, "VideoCapture", lambda *a, **k: _fake_capture())
    monkeypatch.setattr(clipper, "build_face_detectors", lambda: None)
    monkeypatch.setattr(clipper, "detect_scene_cuts", lambda *a, **k: [7.5])
    monkeypatch.setattr(clipper, "faces_in_frame", lambda *a, **k: [])

    clip = clipper.ClipCandidate(index=1, start=0.0, end=20.0, duration=20.0,
                                 score=1, title="t", reason="r", text="x")
    assert clipper.detect_focus_track(video, clip) is None


def test_a_shot_with_nobody_in_it_holds_the_previous_framing(monkeypatch, tmp_path):
    """A graphic or cutaway must not snap the crop somewhere arbitrary."""
    cv2 = pytest.importorskip("cv2")
    video = tmp_path / "v.mp4"
    video.touch()
    monkeypatch.setattr(clipper, "get_video_size", lambda p: (1920, 1080))
    monkeypatch.setattr(cv2, "VideoCapture", lambda *a, **k: _fake_capture())
    monkeypatch.setattr(clipper, "build_face_detectors", lambda: None)
    monkeypatch.setattr(clipper, "detect_scene_cuts", lambda *a, **k: [8.0, 16.0])

    calls = {"n": 0}

    def faces(*args, **kwargs):
        calls["n"] += 1
        # First shot has a face on the right; the graphic shot has none.
        return [(1536.0, 540.0, 200.0, 3.0)] if calls["n"] == 1 else []

    monkeypatch.setattr(clipper, "faces_in_frame", faces)

    clip = clipper.ClipCandidate(index=1, start=0.0, end=24.0, duration=24.0,
                                 score=1, title="t", reason="r", text="x")
    tracked = clipper.detect_focus_track(video, clip)
    assert tracked is not None
    segments, _ = tracked
    assert segments[-1][1] == 24.0
    assert all(focus == pytest.approx(0.8, abs=0.01) for _, _, focus in segments)
