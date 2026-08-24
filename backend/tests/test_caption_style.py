from clipper import (
    AVAILABLE_FONTS,
    CaptionStyle,
    _hex_to_ass_color,
    build_subtitle_style,
)


def test_hex_to_ass_color_basic():
    # ASS uses &HAABBGGRR. White stays white, alpha 00.
    assert _hex_to_ass_color("#FFFFFF") == "&H00FFFFFF"
    # Pure red -> BGR puts red last.
    assert _hex_to_ass_color("#FF0000") == "&H000000FF"
    # Pure blue -> blue first.
    assert _hex_to_ass_color("#0000FF") == "&H00FF0000"


def test_hex_to_ass_color_shorthand():
    assert _hex_to_ass_color("#FFF") == "&H00FFFFFF"


def test_hex_to_ass_color_invalid_falls_back():
    assert _hex_to_ass_color("nonsense") == "&H00FFFFFF"


def test_build_subtitle_style_center_default():
    style = build_subtitle_style(CaptionStyle())
    # ASS alignment 10 is the true vertical middle (5 is top-center in libass).
    assert "Alignment=10" in style
    assert "FontName=DejaVu Sans" in style
    assert "FontSize=30" in style


def test_build_subtitle_style_bottom():
    style = build_subtitle_style(CaptionStyle(position="bottom"))
    assert "Alignment=2" in style
    assert "MarginV=24" in style


def test_build_subtitle_style_font_whitelist():
    style = build_subtitle_style(CaptionStyle(font_family="Liberation Serif"))
    assert "FontName=Liberation Serif" in style
    # Unknown font falls back to default.
    bad = build_subtitle_style(CaptionStyle(font_family="Comic Sans; rm -rf"))
    assert "FontName=DejaVu Sans" in bad


def test_build_subtitle_style_outline_clamped():
    style = build_subtitle_style(CaptionStyle(outline_width=999))
    assert "Outline=8" in style
    style_zero = build_subtitle_style(CaptionStyle(outline_width=-5))
    assert "Outline=0" in style_zero


def test_build_subtitle_style_font_size_clamped():
    assert "FontSize=6" in build_subtitle_style(CaptionStyle(font_size=2))
    assert "FontSize=120" in build_subtitle_style(CaptionStyle(font_size=500))


def test_available_fonts_has_defaults():
    assert "DejaVu Sans" in AVAILABLE_FONTS
    assert "Noto Sans" in AVAILABLE_FONTS


# --- Caption style presets -------------------------------------------------


def test_preset_classic_default_unchanged():
    style = build_subtitle_style(CaptionStyle())
    assert "BorderStyle=1" in style
    assert "Bold=1" in style
    assert "Shadow=1" in style
    assert "Outline=2.0" in style
    assert "BackColour" not in style


def test_preset_bold_adds_outline():
    style = build_subtitle_style(CaptionStyle(style="bold"))
    assert "Bold=1" in style
    # default outline 2.0 + 1
    assert "Outline=3.0" in style
    assert "BorderStyle=1" in style


def test_preset_bold_outline_clamped_to_8():
    style = build_subtitle_style(CaptionStyle(style="bold", outline_width=8))
    assert "Outline=8.0" in style
    style_huge = build_subtitle_style(CaptionStyle(style="bold", outline_width=999))
    assert "Outline=8.0" in style_huge


def test_preset_boxed_uses_opaque_box_backing():
    style = build_subtitle_style(CaptionStyle(style="boxed"))
    assert "BorderStyle=3" in style
    # black box at ~60% opacity -> ASS alpha 0x66 (inverted: 00=opaque)
    assert "BackColour=&H66000000" in style
    assert "Outline=0" in style
    assert "Shadow=0" in style


def test_preset_boxed_backcolour_follows_outline_color():
    style = build_subtitle_style(CaptionStyle(style="boxed", outline_color="#FF0000"))
    # red in BGR order with 0x66 alpha
    assert "BackColour=&H660000FF" in style


def test_preset_highlight_is_translucent_box_and_bold():
    style = build_subtitle_style(CaptionStyle(style="highlight"))
    assert "BorderStyle=3" in style
    # ~40% opacity -> ASS alpha 0x99
    assert "BackColour=&H99000000" in style
    assert "Bold=1" in style
    assert "Outline=0" in style


def test_preset_shadow_no_box():
    style = build_subtitle_style(CaptionStyle(style="shadow"))
    assert "Shadow=2" in style
    assert "Outline=1" in style
    assert "BorderStyle=1" in style
    assert "BackColour" not in style


def test_preset_unknown_falls_back_to_classic():
    style = build_subtitle_style(CaptionStyle(style="neon"))  # type: ignore[arg-type]
    assert "BorderStyle=1" in style
    assert "Outline=2.0" in style
    assert "BackColour" not in style


def test_preset_respects_position_margins():
    bottom = build_subtitle_style(CaptionStyle(style="boxed", position="bottom"))
    assert "Alignment=2" in bottom
    assert "MarginV=24" in bottom
