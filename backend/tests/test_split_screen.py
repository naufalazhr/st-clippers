from clipper import (
    SPLIT_ACTIVITY_HEIGHT,
    SPLIT_FACE_HEIGHT,
    split_screen_filter,
)


def test_split_panels_sum_to_full_height():
    assert SPLIT_FACE_HEIGHT + SPLIT_ACTIVITY_HEIGHT == 1920


def test_split_screen_filter_structure():
    vf = split_screen_filter(1920, 1080, (960.0, 540.0, 200.0))
    # Must split into face + activity branches, blur-fill the activity panel, then vstack.
    assert "split=2[fsplit][asplit]" in vf
    assert f"scale=1080:{SPLIT_FACE_HEIGHT}" in vf
    assert f"scale=1080:{SPLIT_ACTIVITY_HEIGHT}" in vf
    assert "boxblur=20:5" in vf
    assert "vstack=inputs=2" in vf


def test_split_screen_face_crop_within_bounds():
    src_w, src_h = 1920, 1080
    vf = split_screen_filter(src_w, src_h, (100.0, 100.0, 400.0))
    face_crop = vf.split("[fsplit]crop=")[1].split(",")[0]
    w, h, x, y = (int(p) for p in face_crop.split(":"))
    assert 16 <= w <= src_w
    assert 16 <= h <= src_h
    assert 0 <= x <= src_w - w
    assert 0 <= y <= src_h - y - h or y >= 0


def test_split_screen_face_panel_centers_on_face():
    src_w, src_h = 1920, 1080
    cx, cy, size = 1400.0, 600.0, 240.0
    vf = split_screen_filter(src_w, src_h, (cx, cy, size))
    face_crop = vf.split("[fsplit]crop=")[1].split(",")[0]
    w, h, x, y = (int(p) for p in face_crop.split(":"))
    # Face centre should land inside the crop box.
    assert x <= cx <= x + w
    assert y <= cy <= y + h


def test_split_screen_no_face_fallback_is_valid():
    vf = split_screen_filter(1920, 1080, None)
    assert "vstack=inputs=2" in vf
    face_crop = vf.split("[fsplit]crop=")[1].split(",")[0]
    w, h, x, y = (int(p) for p in face_crop.split(":"))
    assert x == 0  # full-width centred slice when nothing detected
    assert w == 1920


def test_split_screen_activity_panel_keeps_full_frame():
    vf = split_screen_filter(1920, 1080, (960.0, 540.0, 200.0))
    # Activity branch must contain a decrease-fit scale (whole frame visible over blur).
    fit_part = vf.split("[afg]scale=")[1].split("[afit]")[0]
    assert "force_original_aspect_ratio=decrease" in fit_part
