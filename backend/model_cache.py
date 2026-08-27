from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

DOWNLOAD_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 3


class ModelDownloadError(RuntimeError):
    """Raised when the transcription model cannot be fetched."""


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
    """True only when the weights are actually on disk.

    An interrupted snapshot still leaves the small metadata files behind
    (config.json, tokenizer.json, ...). Treating "directory is not empty" as
    cached made a partial download poison the cache permanently: every later run
    skipped the download and then failed to load the missing weights.
    """
    p = model_cache_dir(data_dir, model_name)
    if not p.is_dir():
        return False
    has_weights = any(p.glob("model*.bin"))
    return has_weights and (p / "config.json").is_file()


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
            return _download_with_retries(model_name, data_dir, local)
        finally:
            _progress["value"] = None


def _download_with_retries(model_name: str, data_dir: Path, local: Path) -> str:
    """Download the model, retrying interrupted transfers.

    Large weight files get aborted mid-stream often enough on Windows (security
    software closing long-lived connections shows up as WinError 10053) that a
    single attempt is not enough. Partial files are deliberately left in place:
    huggingface_hub resumes from them on the next attempt.
    """
    from huggingface_hub import snapshot_download

    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            snapshot_download(
                repo_id=model_name,
                local_dir=str(local),
                local_dir_use_symlinks=False,
            )
        except Exception as exc:  # network/IO failures are all retryable here
            last_error = exc
            print(
                f"[model] Download attempt {attempt}/{DOWNLOAD_ATTEMPTS} failed: {exc}",
                flush=True,
            )
        else:
            if model_present(data_dir, model_name):
                return str(local)
            last_error = RuntimeError("download completed but the weights are missing")
            print(f"[model] Attempt {attempt}: {last_error}", flush=True)

        if attempt < DOWNLOAD_ATTEMPTS:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise ModelDownloadError(
        f"Could not download the transcription model '{model_name}' after "
        f"{DOWNLOAD_ATTEMPTS} attempts. The connection kept dropping partway "
        "through. Check your internet connection, and any antivirus, firewall "
        "or VPN that may be interrupting large downloads, then try again "
        f"(finished parts are kept and resumed). Last error: {last_error}"
    ) from last_error
