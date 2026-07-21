from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

_lock = threading.Lock()
_progress: dict[str, float | None] = {"value": None}
_current_model: str = "Systran/faster-whisper-small"


def resolve_data_dir() -> Path:
    env = os.environ.get("SULTANCLIP_DATA_DIR")
    if env:
        return Path(env)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SultanClip"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "SultanClip"
    return Path(__file__).resolve().parent


def model_cache_dir(data_dir: Path, model_name: str) -> Path:
    safe = model_name.replace("/", "--")
    return data_dir / "models" / safe


def model_present(data_dir: Path, model_name: str) -> bool:
    p = model_cache_dir(data_dir, model_name)
    return p.is_dir() and any(p.iterdir())


def get_download_progress() -> float | None:
    return _progress["value"]


def get_current_model() -> str:
    return _current_model


def ensure_model(model_name: str, data_dir: Path) -> str:
    global _current_model
    _current_model = model_name
    local = model_cache_dir(data_dir, model_name)
    if model_present(data_dir, model_name):
        _progress["value"] = None
        return str(local)

    with _lock:
        if model_present(data_dir, model_name):
            _progress["value"] = None
            return str(local)

        local.mkdir(parents=True, exist_ok=True)
        _progress["value"] = 0.0
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(
                repo_id=model_name,
                local_dir=str(local),
                local_dir_use_symlinks=False,
            )
            _progress["value"] = None
            return str(local)
        except Exception:
            _progress["value"] = None
            raise
