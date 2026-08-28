"""Keep the test suite away from the real application data directory.

api.py and model_cache.py resolve their data directory at import time, so this
has to run before pytest imports any test module -- conftest is imported first,
which is why it lives here rather than in a fixture.

Without it the suite writes its fixture jobs into %APPDATA%/SultanClip (or
~/Library/Application Support/SultanClip) and can clobber a real job list,
including one belonging to a job that is currently running.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.gettempdir()) / "sultanclip-test-data"
_TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

# setdefault so CI or a developer can still point the suite somewhere specific.
os.environ.setdefault("SULTANCLIP_DATA_DIR", str(_TEST_DATA_DIR))
