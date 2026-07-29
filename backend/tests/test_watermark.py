from pathlib import Path

import pytest

from clipper import (
    WATERMARK_POSITIONS,
    WatermarkStyle,
    build_watermark_filter,
)


@pytest.fixture()
def tmp_clips(tmp_path):
    return tmp_path


def test_text_filter_returns_drawtext(tmp_clips):
    wm = WatermarkStyle(text="Hello")
    result = build_watermark_filter(wm, tmp_clips)
    assert result.startswith("drawtext=")
    assert "textfile=" in result


def test_text_filter_writes_textfile(tmp_clips):
    wm = WatermarkStyle(text="My Brand")
    build_watermark_filter(wm, tmp_clips)
    assert (tmp_clips / "_wm_text.txt").read_text() == "My Brand"


def test_text_injection_newline_stripped(tmp_clips):
    wm = WatermarkStyle(text="line1\nline2")
    build_watermark_filter(wm, tmp_clips)
    content = (tmp_clips / "_wm_text.txt").read_text()
    assert "\n" not in content
    assert "line1" in content


def test_text_filter_contains_color(tmp_clips):
    wm = WatermarkStyle(text="X", color="#FF0000")
    result = build_watermark_filter(wm, tmp_clips)
    assert "fontcolor=#FF0000" in result


def test_text_filter_shorthand_color_expanded(tmp_clips):
    wm = WatermarkStyle(text="X", color="#FFF")
    result = build_watermark_filter(wm, tmp_clips)
    assert "fontcolor=#FFFFFF" in result


def test_text_filter_invalid_color_falls_back(tmp_clips):
    wm = WatermarkStyle(text="X", color="notacolor")
    result = build_watermark_filter(wm, tmp_clips)
    assert "fontcolor=#FFFFFF" in result


def test_text_filter_opacity_in_filter(tmp_clips):
    wm = WatermarkStyle(text="X", opacity=0.5)
    result = build_watermark_filter(wm, tmp_clips)
    assert "alpha=0.5" in result


def test_text_filter_full_opacity_omits_alpha(tmp_clips):
    wm = WatermarkStyle(text="X", opacity=1.0)
    result = build_watermark_filter(wm, tmp_clips)
    assert "alpha=" not in result


def test_text_filter_position_bottom_left(tmp_clips):
    wm = WatermarkStyle(text="X", position="bottom-left")
    result = build_watermark_filter(wm, tmp_clips)
    assert "x=main_w*" in result
    assert "y=main_h-overlay_h" in result


def test_text_filter_unknown_position_falls_back(tmp_clips):
    wm = WatermarkStyle(text="X", position="invalid-pos")
    result = build_watermark_filter(wm, tmp_clips)
    assert result.startswith("drawtext=")


def test_image_filter_returns_fc_sentinel(tmp_clips):
    img = tmp_clips / "logo.png"
    img.write_bytes(b"")
    wm = WatermarkStyle(image_path=img)
    result = build_watermark_filter(wm, tmp_clips)
    assert result.startswith("_fc:")


def test_image_filter_uses_absolute_path(tmp_clips):
    img = tmp_clips / "logo.png"
    img.write_bytes(b"")
    wm = WatermarkStyle(image_path=img)
    result = build_watermark_filter(wm, tmp_clips)
    fc = result[len("_fc:"):]
    assert str(img.resolve()) not in fc


def test_image_filter_contains_overlay(tmp_clips):
    img = tmp_clips / "logo.png"
    img.write_bytes(b"")
    wm = WatermarkStyle(image_path=img)
    result = build_watermark_filter(wm, tmp_clips)
    assert "overlay=" in result


def test_image_filter_scale(tmp_clips):
    img = tmp_clips / "logo.png"
    img.write_bytes(b"")
    wm = WatermarkStyle(image_path=img, scale=50)
    result = build_watermark_filter(wm, tmp_clips)
    assert "scale=iw*0.5000" in result


def test_image_filter_opacity(tmp_clips):
    img = tmp_clips / "logo.png"
    img.write_bytes(b"")
    wm = WatermarkStyle(image_path=img, opacity=0.3)
    result = build_watermark_filter(wm, tmp_clips)
    assert "aa=0.3000" in result


def test_none_watermark_returns_empty(tmp_clips):
    wm = WatermarkStyle()
    result = build_watermark_filter(wm, tmp_clips)
    assert result == ""


def test_all_positions_produce_valid_filter(tmp_clips):
    for pos in WATERMARK_POSITIONS:
        wm = WatermarkStyle(text="T", position=pos)
        result = build_watermark_filter(wm, tmp_clips)
        assert result.startswith("drawtext="), f"failed for position {pos}"
