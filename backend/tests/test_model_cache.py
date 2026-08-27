"""Guards against a partial model download poisoning the cache."""
from __future__ import annotations

import sys

import pytest

import model_cache
from model_cache import (
    ModelDownloadError,
    ensure_model,
    model_cache_dir,
    model_present,
)

MODEL = "Systran/faster-whisper-small"


def _make_cache(tmp_path, *names):
    d = model_cache_dir(tmp_path, MODEL)
    d.mkdir(parents=True, exist_ok=True)
    for name in names:
        (d / name).write_bytes(b"x")
    return d


def _fake_hub(monkeypatch, fn):
    monkeypatch.setattr(model_cache, "RETRY_BACKOFF_SECONDS", 0)
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        type("m", (), {"snapshot_download": staticmethod(fn)}),
    )


def test_partial_download_is_not_reported_as_present(tmp_path):
    # Exactly what an interrupted snapshot leaves behind: metadata but no
    # weights. "directory is not empty" called this cached forever.
    _make_cache(tmp_path, "config.json", "tokenizer.json", "vocabulary.txt", "README.md")
    assert model_present(tmp_path, MODEL) is False


def test_complete_download_is_present(tmp_path):
    _make_cache(tmp_path, "config.json", "tokenizer.json", "model.bin")
    assert model_present(tmp_path, MODEL) is True


def test_weights_without_config_are_not_present(tmp_path):
    _make_cache(tmp_path, "model.bin")
    assert model_present(tmp_path, MODEL) is False


def test_missing_directory_is_not_present(tmp_path):
    assert model_present(tmp_path, MODEL) is False


def test_download_retries_and_succeeds(tmp_path, monkeypatch):
    calls = {"n": 0}

    def flaky(repo_id, local_dir, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("[WinError 10053] connection aborted")
        _make_cache(tmp_path, "config.json", "model.bin")

    _fake_hub(monkeypatch, flaky)
    path = ensure_model(MODEL, tmp_path)
    assert calls["n"] == 3
    assert model_present(tmp_path, MODEL)
    assert str(model_cache_dir(tmp_path, MODEL)) == path


def test_persistent_failure_raises_an_actionable_error(tmp_path, monkeypatch):
    def always_fails(repo_id, local_dir, **kwargs):
        raise OSError("[WinError 10053] connection aborted")

    _fake_hub(monkeypatch, always_fails)
    with pytest.raises(ModelDownloadError) as excinfo:
        ensure_model(MODEL, tmp_path)
    message = str(excinfo.value)
    assert "antivirus" in message and "resumed" in message
    assert model_cache.get_download_progress() is None


def test_download_that_leaves_no_weights_is_treated_as_failure(tmp_path, monkeypatch):
    def writes_only_metadata(repo_id, local_dir, **kwargs):
        _make_cache(tmp_path, "config.json", "tokenizer.json")

    _fake_hub(monkeypatch, writes_only_metadata)
    with pytest.raises(ModelDownloadError):
        ensure_model(MODEL, tmp_path)
