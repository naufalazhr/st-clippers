"""Tests for HOGDescriptor crash fallback in detect_person_focus_x."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clipper import (
    CENTER_CROP_FILTER,
    ClipCandidate,
    detect_person_focus_x,
    vertical_crop_filter,
)


@pytest.fixture
def dummy_clip():
    return ClipCandidate(index=0, start=0.0, end=10.0, duration=10.0, score=50, title="t", reason="r", text="hello")


def _make_cv2_mock(hog_side_effect):
    """Return a cv2 mock where HOGDescriptor raises the given exception."""
    cv2 = MagicMock()
    cv2.VideoCapture.return_value.isOpened.return_value = True
    cv2.VideoCapture.return_value.get.return_value = 1280  # width / height
    cv2.HOGDescriptor.side_effect = hog_side_effect
    return cv2


def test_detect_person_returns_none_on_attribute_error(dummy_clip, tmp_path):
    fake_video = tmp_path / "v.mp4"
    fake_video.touch()
    cv2_mock = _make_cv2_mock(AttributeError("HOGDescriptor API changed"))

    with patch.dict("sys.modules", {"cv2": cv2_mock}):
        result = detect_person_focus_x(fake_video, dummy_clip)

    assert result is None


def test_detect_person_returns_none_on_runtime_error(dummy_clip, tmp_path):
    fake_video = tmp_path / "v.mp4"
    fake_video.touch()
    cv2_mock = _make_cv2_mock(RuntimeError("model file not found"))

    with patch.dict("sys.modules", {"cv2": cv2_mock}):
        result = detect_person_focus_x(fake_video, dummy_clip)

    assert result is None


def test_vertical_crop_filter_falls_back_to_center_when_detect_returns_none(dummy_clip, tmp_path):
    fake_video = tmp_path / "v.mp4"
    fake_video.touch()
    with patch("clipper.detect_focus_track", return_value=None):
        result = vertical_crop_filter(fake_video, dummy_clip, "person")

    assert result == CENTER_CROP_FILTER
