import os
from pathlib import Path


def test_resolve_data_dir_env_override():
    from api import resolve_data_dir

    os.environ["SULTANCLIP_DATA_DIR"] = "/tmp/sultanclip-test"
    try:
        result = resolve_data_dir()
        assert result == Path("/tmp/sultanclip-test")
    finally:
        del os.environ["SULTANCLIP_DATA_DIR"]


def test_resolve_data_dir_returns_path():
    from api import resolve_data_dir

    result = resolve_data_dir()
    assert isinstance(result, Path)
    assert result.is_dir()
