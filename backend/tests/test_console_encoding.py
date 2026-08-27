"""Non-Latin-1 text must never crash the pipeline on Windows."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent

# Characters that broke real runs: U+2011 came back from the LLM, and transcripts
# routinely contain smart quotes, dashes and emoji.
TRICKY = ["Ini‑judul", "“quoted”", "em—dash", "emoji \U0001f3ac", "Hało"]


def test_entry_point_forces_utf8_streams():
    source = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "_force_utf8_streams" in source
    assert 'encoding="utf-8"' in source
    # Must run at import time, before clipper's Console is constructed.
    assert source.index("_force_utf8_streams()") < source.index("def main(")


def test_console_does_not_use_the_win32_legacy_writer():
    # rich's legacy Windows renderer bypasses sys.stdout and encodes as cp1252,
    # so a UTF-8 stream alone is not enough.
    source = (BACKEND / "clipper.py").read_text(encoding="utf-8")
    assert "Console(legacy_windows=False)" in source


def test_subprocess_env_requests_utf8():
    source = (BACKEND / "api.py").read_text(encoding="utf-8")
    assert 'env["PYTHONIOENCODING"] = "utf-8"' in source
    assert 'env["PYTHONUTF8"] = "1"' in source


@pytest.mark.parametrize("text", TRICKY)
def test_rich_console_survives_a_cp1252_stream(text):
    from rich.console import Console

    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    # Apply the same treatment main.py gives the real streams.
    stream.reconfigure(encoding="utf-8", errors="replace")
    Console(legacy_windows=False, file=stream).print(f"[green]Clip:[/green] {text}")
    stream.flush()
    assert text.encode("utf-8") in raw.getvalue()


@pytest.mark.parametrize("text", TRICKY)
def test_reconfigured_stream_round_trips(text):
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    stream.reconfigure(encoding="utf-8", errors="replace")
    print(text, file=stream)
    stream.flush()
    assert raw.getvalue().decode("utf-8").strip() == text
