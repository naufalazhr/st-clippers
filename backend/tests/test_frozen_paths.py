from pathlib import Path
import sys


def test_frozen_base_dev_mode():
    from clipper import frozen_base

    result = frozen_base()
    assert isinstance(result, Path)
    assert result.name == "backend"


def test_frozen_base_frozen_mode():
    import clipper

    old_frozen = getattr(sys, "frozen", False)
    old_meipass = getattr(sys, "_MEIPASS", None)
    try:
        sys.frozen = True
        sys._MEIPASS = "/tmp/fakebundle"
        assert clipper.frozen_base() == Path("/tmp/fakebundle")
    finally:
        if old_frozen:
            sys.frozen = old_frozen
        else:
            del sys.frozen
        if old_meipass:
            sys._MEIPASS = old_meipass
        else:
            del sys._MEIPASS


def test_yunet_path_dev_mode():
    from clipper import YUNET_MODEL_PATH, frozen_base

    assert YUNET_MODEL_PATH == frozen_base() / "models" / "face_detection_yunet_2023mar.onnx"
