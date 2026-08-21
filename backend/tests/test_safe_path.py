"""The PATH prune that keeps yt-dlp's runtime probe from killing the backend."""
from __future__ import annotations

import os
from unittest.mock import patch

from safe_path import prune_unresolvable_path_entries

BAD = r"C:\Users\yugie\scoop\apps\openssl\current\bin"
GOOD_A = r"C:\Windows\system32"
GOOD_B = r"C:\Program Files\Git\cmd"

# WinError 448: "The path cannot be traversed because it contains an untrusted
# mount point" — what a scoop-style junction raises under Windows' redirection
# trust mitigation.
UNTRUSTED_MOUNT_POINT = OSError(22, "untrusted mount point", BAD, 448)


def _realpath_raising_on_bad(path, *args, **kwargs):
    if path == BAD:
        raise UNTRUSTED_MOUNT_POINT
    return path


def test_drops_only_the_unresolvable_entry(monkeypatch):
    monkeypatch.setenv("PATH", os.pathsep.join([GOOD_A, BAD, GOOD_B]))
    with patch("os.path.realpath", side_effect=_realpath_raising_on_bad):
        dropped = prune_unresolvable_path_entries()

    assert dropped == [BAD]
    assert os.environ["PATH"].split(os.pathsep) == [GOOD_A, GOOD_B]


def test_leaves_a_healthy_path_untouched(monkeypatch):
    original = os.pathsep.join([GOOD_A, GOOD_B])
    monkeypatch.setenv("PATH", original)
    with patch("os.path.realpath", side_effect=_realpath_raising_on_bad):
        assert prune_unresolvable_path_entries() == []
    assert os.environ["PATH"] == original


def test_handles_empty_and_missing_path(monkeypatch):
    monkeypatch.delenv("PATH", raising=False)
    assert prune_unresolvable_path_entries() == []
    monkeypatch.setenv("PATH", "")
    assert prune_unresolvable_path_entries() == []


def test_yt_dlp_runtime_probe_survives_the_bad_entry(monkeypatch):
    """The real failure: yt-dlp maps realpath over PATH without guarding it."""
    jsruntime = __import__("yt_dlp.utils._jsruntime", fromlist=["_find_exe"])
    if os.name != "nt":  # _find_exe returns before scanning PATH elsewhere
        return

    monkeypatch.setenv("PATH", os.pathsep.join([GOOD_A, BAD]))
    with patch("os.path.realpath", side_effect=_realpath_raising_on_bad):
        try:
            jsruntime._find_exe("deno")
        except OSError as exc:
            assert exc.winerror == 448  # reproduces the reported crash
        else:
            raise AssertionError("expected the unguarded realpath to raise")

        prune_unresolvable_path_entries()
        jsruntime._find_exe("deno")  # no longer raises
