"""Guards for the settings that decide output sharpness."""
from __future__ import annotations

import clipper
from clipper import (
    CENTER_CROP_FILTER,
    SCALE_FLAGS,
    source_format_ladder,
    streamer_stack_filter,
    vertical_crop_filter,
)


def test_format_ladder_prefers_high_resolution_over_progressive():
    ladder = source_format_ladder(2160)
    options = ladder.split("/")
    # Progressive formats cap at 720p on YouTube, so they must never win over a
    # separate video+audio stream.
    assert options[0].startswith("bestvideo[height<=2160]")
    assert options.index("best") == len(options) - 1
    assert options.index("bestvideo+bestaudio") < options.index("best")


def test_format_ladder_is_not_capped_at_1080p():
    assert clipper.MAX_SOURCE_HEIGHT >= 2160
    assert "height<=1080" not in source_format_ladder(clipper.MAX_SOURCE_HEIGHT)


def test_every_geometry_scale_uses_lanczos(dummy_clip=None):
    streamer = streamer_stack_filter(1920, 1080, "br")
    for filter_str in (CENTER_CROP_FILTER, streamer):
        for chunk in filter_str.split(";"):
            for part in chunk.split(","):
                if part.strip().startswith("scale="):
                    assert f"flags={SCALE_FLAGS}" in part, part


def test_person_crop_scale_uses_lanczos(tmp_path):
    from unittest.mock import patch

    clip = clipper.ClipCandidate(
        index=0, start=0.0, end=10.0, duration=10.0, score=1, title="t", reason="r", text="x"
    )
    video = tmp_path / "v.mp4"
    video.touch()
    with patch("clipper.detect_person_focus_x", return_value=(0.5, (1920, 1080))):
        vf = vertical_crop_filter(video, clip, "person")
    assert f"flags={SCALE_FLAGS}" in vf.split(",")[0]


def test_encoder_uses_high_profile_without_a_level_bitrate_ceiling():
    source = (clipper.__file__).replace(".pyc", ".py")
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    # baseline drops CABAC and the 8x8 transform, which costs fine detail. Pinning
    # "-level 4.0" also mis-tagged 60fps 1080x1920 clips: their macroblock rate
    # (489600) is nearly double that level's limit (245760), so the file claimed a
    # level it did not conform to. Auto-selection tags 4.2 correctly.
    assert '"baseline"' not in text
    assert '"-level"' not in text
    assert text.count('"high"') >= 2


def _select(format_spec, formats, format_sort=None):
    """Resolve a format spec against fake formats, offline."""
    from yt_dlp import YoutubeDL

    opts = {"quiet": True, "no_warnings": True, "simulate": True}
    if format_sort:
        opts["format_sort"] = format_sort
    ydl = YoutubeDL(opts)
    selector = getattr(ydl, "build_format_selector", None)
    if selector is None:  # yt-dlp internals moved; nothing to assert against
        import pytest

        pytest.skip("yt_dlp.build_format_selector is unavailable")
    chosen = list(selector(format_spec)({"formats": formats, "incomplete_formats": {}}))
    picked = []
    for result in chosen:
        picked += result.get("requested_formats") or [result]
    return picked


def _fmt(format_id, height, vcodec, ext, acodec="none"):
    return {
        "format_id": format_id,
        "ext": ext,
        "height": height,
        "vcodec": vcodec,
        "acodec": acodec,
        "url": "http://example.invalid",
    }


M4A = _fmt("140", None, "none", "m4a", "mp4a")
OPUS = _fmt("251", None, "none", "webm", "opus")


def test_4k_source_is_preferred_over_a_1080p_mp4():
    # The 4K rendition is webm, so an "[ext=mp4]" preference would have quietly
    # kept the 1080p stream and upscaled it.
    formats = [
        _fmt("22", 720, "avc1", "mp4", "mp4a"),
        _fmt("137", 1080, "avc1", "mp4"),
        _fmt("315", 2160, "vp9", "webm"),
        M4A,
        OPUS,
    ]
    picked = _select(source_format_ladder(2160), formats, clipper.SOURCE_FORMAT_SORT)
    assert [f["format_id"] for f in picked] == ["315", "140"]


def test_av1_is_avoided_when_another_codec_matches_the_resolution():
    formats = [
        _fmt("137", 1080, "avc1", "mp4"),
        _fmt("401", 2160, "av01", "mp4"),
        _fmt("315", 2160, "vp9", "webm"),
        M4A,
    ]
    picked = _select(source_format_ladder(2160), formats, clipper.SOURCE_FORMAT_SORT)
    assert picked[0]["format_id"] == "315"


def test_selection_is_capped_and_unchanged_for_a_1080p_only_video():
    formats = [
        _fmt("18", 360, "avc1", "mp4", "mp4a"),
        _fmt("22", 720, "avc1", "mp4", "mp4a"),
        _fmt("137", 1080, "avc1", "mp4"),
        M4A,
        OPUS,
    ]
    picked = _select(source_format_ladder(2160), formats, clipper.SOURCE_FORMAT_SORT)
    assert [f["format_id"] for f in picked] == ["137", "140"]

    over_cap = [*formats, _fmt("571", 4320, "vp9", "webm")]
    picked = _select(source_format_ladder(2160), over_cap, clipper.SOURCE_FORMAT_SORT)
    assert picked[0]["height"] <= 2160
