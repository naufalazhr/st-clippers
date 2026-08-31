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
    # libass paints the box with OutlineColour; BackColour only tints the shadow.
    # "boxed" defaults to solid (ASS alpha is inverted, so 00 = opaque).
    assert "OutlineColour=&H00000000" in style
    # Outline is the box padding -- at 0 libass draws no box at all.
    assert float(style.split("Outline=")[1].split(",")[0]) > 0
    assert "Shadow=0" in style


def test_preset_boxed_box_colour_follows_outline_color():
    style = build_subtitle_style(CaptionStyle(style="boxed", outline_color="#FF0000"))
    # red in BGR order, solid by default
    assert "OutlineColour=&H000000FF" in style


def test_preset_highlight_is_translucent_box_and_bold():
    style = build_subtitle_style(CaptionStyle(style="highlight"))
    assert "BorderStyle=3" in style
    # highlight stays deliberately see-through
    assert "OutlineColour=&H8C000000" in style
    assert "Bold=1" in style
    assert float(style.split("Outline=")[1].split(",")[0]) > 0


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


# --- the selected style/font actually reaching libass ------------------------

def test_boxed_and_highlight_differ():
    from clipper import build_subtitle_style, CaptionStyle

    boxed = build_subtitle_style(CaptionStyle(style="boxed"))
    highlight = build_subtitle_style(CaptionStyle(style="highlight"))
    assert boxed != highlight


def test_box_presets_paint_the_box_with_outline_colour():
    # libass draws the BorderStyle=3 box with OutlineColour; BackColour only
    # tints the shadow, so setting that left both presets looking identical.
    from clipper import build_subtitle_style, CaptionStyle

    style = build_subtitle_style(CaptionStyle(style="boxed", outline_color="#000000"))
    assert "BorderStyle=3" in style
    assert "OutlineColour=&H00000000" in style
    assert "BackColour" not in style


def test_box_presets_keep_padding_so_a_box_is_drawn():
    # Outline doubles as the box padding: at 0 nothing is drawn.
    from clipper import BOX_PADDING_MIN, build_subtitle_style, CaptionStyle

    for preset in ("boxed", "highlight"):
        style = build_subtitle_style(CaptionStyle(style=preset, outline_width=0.0))
        outline = float(style.split("Outline=")[1].split(",")[0])
        assert outline >= BOX_PADDING_MIN, (preset, outline)


def test_every_preset_produces_a_distinct_style():
    from clipper import CAPTION_STYLE_PRESETS, build_subtitle_style, CaptionStyle

    styles = {p: build_subtitle_style(CaptionStyle(style=p)) for p in CAPTION_STYLE_PRESETS}
    assert len(set(styles.values())) == len(styles), styles


def test_font_choice_changes_the_style():
    from clipper import build_subtitle_style, CaptionStyle

    sans = build_subtitle_style(CaptionStyle(font_family="DejaVu Sans"))
    serif = build_subtitle_style(CaptionStyle(font_family="DejaVu Serif"))
    assert sans != serif
    assert "FontName=DejaVu Serif" in serif


def test_bundled_fonts_exist_for_every_offered_choice():
    from clipper import AVAILABLE_FONTS, subtitle_fonts_dir

    fonts_dir = subtitle_fonts_dir()
    assert fonts_dir.is_dir(), fonts_dir
    stems = {p.stem.replace("-Regular", "").replace("-Bold", "") for p in fonts_dir.glob("*.ttf")}
    for label in AVAILABLE_FONTS:
        assert label.replace(" ", "") in {s.replace(" ", "") for s in stems}, label


def test_fontsdir_is_quoted_and_escaped_for_the_filter_graph():
    # A bare Windows path breaks filter parsing: ':' separates filter options.
    from pathlib import Path

    from clipper import ffmpeg_filter_path

    arg = ffmpeg_filter_path(Path(r"C:\app\fonts"))
    assert arg.startswith("'") and arg.endswith("'")
    assert "\:" in arg
    assert "\\\\" not in arg.strip("'")


# --- configurable box opacity ----------------------------------------------

def test_boxed_defaults_to_a_solid_box():
    # A black box at 60% read as washed out over bright footage; "boxed" now
    # means solid unless the user dials it down. ASS alpha is inverted.
    from clipper import build_subtitle_style, CaptionStyle

    style = build_subtitle_style(CaptionStyle(style="boxed", outline_color="#000000"))
    assert "OutlineColour=&H00000000" in style


def test_highlight_stays_translucent_by_default():
    from clipper import build_subtitle_style, CaptionStyle

    style = build_subtitle_style(CaptionStyle(style="highlight", outline_color="#000000"))
    alpha = style.split("OutlineColour=&H")[1][:2]
    assert alpha not in ("00", "FF"), alpha


def test_box_opacity_overrides_the_preset():
    from clipper import build_subtitle_style, CaptionStyle

    solid = build_subtitle_style(CaptionStyle(style="highlight", box_opacity=100))
    assert "OutlineColour=&H00000000" in solid

    faint = build_subtitle_style(CaptionStyle(style="boxed", box_opacity=0))
    assert "OutlineColour=&HFF000000" in faint


def test_box_opacity_is_clamped():
    from clipper import resolve_box_opacity

    assert resolve_box_opacity("boxed", 500) == 1.0
    assert resolve_box_opacity("boxed", -20) == 0.0
    assert resolve_box_opacity("boxed", None) == 1.0
    assert resolve_box_opacity("highlight", None) == 0.45
    assert resolve_box_opacity("classic", None) == 1.0


def test_box_opacity_follows_the_chosen_colour():
    from clipper import build_subtitle_style, CaptionStyle

    style = build_subtitle_style(
        CaptionStyle(style="boxed", outline_color="#FF0000", box_opacity=50)
    )
    # 50% -> alpha 0x80, red in BGR order.
    assert "OutlineColour=&H800000FF" in style


def test_opacity_is_ignored_by_non_box_presets():
    from clipper import build_subtitle_style, CaptionStyle

    for preset in ("classic", "bold", "shadow"):
        a = build_subtitle_style(CaptionStyle(style=preset, box_opacity=10))
        b = build_subtitle_style(CaptionStyle(style=preset, box_opacity=90))
        assert a == b, preset


def test_fontsdir_escapes_an_apostrophe_in_the_path():
    # A user folder like C:\Users\O'Brien would otherwise close the quoted
    # filter option early and break the whole graph.
    from pathlib import Path

    from clipper import ffmpeg_filter_path

    arg = ffmpeg_filter_path(Path(r"C:\Users\O'Brien\fonts"))
    assert arg == r"'C\:/Users/O\'Brien/fonts'"
