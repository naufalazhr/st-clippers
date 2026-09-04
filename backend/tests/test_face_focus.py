"""Choosing where to crop: reject impossible faces, and agree instead of average.

Two defects produced clips with no face in frame:

* detections were ranked by box size with no upper bound, so a single 765px
  "face" (a studio logo) outranked every real 270px face in the same frame;
* per-sample picks were combined with a weighted mean, which for two people on
  opposite sides of a set lands on the empty backdrop between them.
"""
from __future__ import annotations

import pytest

from clipper import (
    MAX_FACE_WIDTH_FRACTION,
    MIN_FACE_WIDTH_FRACTION,
    consensus_focus,
    crop_window_fraction,
    plausible_face,
)

FRAME = 1920
WINDOW = 0.316  # what a 1080x1920 crop keeps of a 1920x1080 source


# --- what counts as a face --------------------------------------------------

def test_real_podcast_faces_are_plausible():
    for box in (120, 180, 270, 350, 500):
        assert plausible_face(box, FRAME), box


def test_the_studio_logo_false_positive_is_rejected():
    # Measured from a real failure: Haar returned a 765px box on a set logo and,
    # being the largest, it won the frame.
    assert not plausible_face(765, FRAME)


def test_noise_specks_are_rejected():
    assert not plausible_face(10, FRAME)


def test_the_bounds_are_inclusive_at_the_edges():
    assert plausible_face(MAX_FACE_WIDTH_FRACTION * FRAME, FRAME)
    assert plausible_face(MIN_FACE_WIDTH_FRACTION * FRAME, FRAME)
    assert not plausible_face(MAX_FACE_WIDTH_FRACTION * FRAME + 1, FRAME)


def test_bounds_scale_with_frame_width():
    # 400px is a face in 1920 but a backdrop in 720.
    assert plausible_face(400, FRAME)
    assert not plausible_face(400, 720)


def test_a_zero_width_frame_never_validates():
    assert not plausible_face(100, 0)


# --- agreeing on a focus ----------------------------------------------------

def test_one_speaker_is_followed():
    picks = [(0.30, 1.0), (0.32, 1.0), (0.29, 1.0)]
    assert consensus_focus(picks, WINDOW) == pytest.approx(0.303, abs=0.01)


def test_two_people_do_not_average_into_the_gap():
    """The bug in one line: the mean of 0.2 and 0.8 is the backdrop."""
    picks = [(0.2, 1.0), (0.8, 1.0), (0.2, 1.0), (0.8, 1.0), (0.2, 1.0)]
    mean = sum(x * w for x, w in picks) / sum(w for _, w in picks)
    assert mean == pytest.approx(0.44)  # what the old code produced

    focus = consensus_focus(picks, WINDOW)
    assert focus == pytest.approx(0.2)  # a face that is really there
    # Whatever it picks must be a place a face actually was.
    assert any(abs(focus - x) <= WINDOW / 2 for x, _ in picks)


def test_the_busier_side_wins():
    picks = [(0.25, 1.0), (0.25, 1.0), (0.25, 1.0), (0.75, 1.0)]
    assert consensus_focus(picks, WINDOW) == pytest.approx(0.25)


def test_a_lone_outlier_does_not_drag_the_focus():
    picks = [(0.60, 1.0), (0.62, 1.0), (0.61, 1.0), (0.05, 1.0)]
    focus = consensus_focus(picks, WINDOW)
    assert focus == pytest.approx(0.61, abs=0.02)


def test_weight_breaks_a_numeric_tie():
    # One confident close-up beats one weak detection on the far side.
    picks = [(0.25, 5.0), (0.75, 1.0)]
    assert consensus_focus(picks, WINDOW) == pytest.approx(0.25)


def test_the_focus_is_refined_within_its_cluster():
    # Members of the winning cluster are averaged, so small movement is tracked.
    picks = [(0.40, 1.0), (0.44, 1.0)]
    assert consensus_focus(picks, WINDOW) == pytest.approx(0.42)


def test_no_picks_means_no_focus():
    assert consensus_focus([], WINDOW) is None


def test_zero_weight_picks_do_not_divide_by_zero():
    assert consensus_focus([(0.5, 0.0)], WINDOW) is None


def test_a_single_pick_is_used_as_is():
    assert consensus_focus([(0.73, 2.0)], WINDOW) == pytest.approx(0.73)


# --- the crop window --------------------------------------------------------

def test_crop_window_for_a_landscape_source():
    # A 9:16 crop of 16:9 keeps ~32% of the width; that is how far apart two
    # detections can be and still both fit in frame.
    assert crop_window_fraction(1920, 1080) == pytest.approx(0.316, abs=0.005)


def test_crop_window_for_an_already_vertical_source():
    # Nothing is cut horizontally, so the whole width is in frame.
    assert crop_window_fraction(1080, 1920) == pytest.approx(1.0)


def test_crop_window_survives_a_degenerate_size():
    assert crop_window_fraction(0, 0) == 1.0


def test_wider_sources_keep_proportionally_less():
    assert crop_window_fraction(3840, 1080) < crop_window_fraction(1920, 1080)
