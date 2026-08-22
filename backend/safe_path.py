r"""Keep PATH entries this process cannot resolve from crashing yt-dlp.

yt-dlp looks for a JavaScript runtime by mapping os.path.realpath over every
PATH entry (yt_dlp/utils/_jsruntime.py, Windows only). That call is unguarded,
so a single unresolvable entry raises out of extract_info and takes the whole
backend down:

    OSError: [WinError 448] The path cannot be traversed because it contains an
    untrusted mount point: 'C:\Users\...\scoop\apps\openssl\current\bin'

Directory junctions like scoop's "current" links hit this whenever the process
runs under Windows' redirection-trust mitigation. Such an entry is unusable to
this process anyway, so drop it before yt-dlp ever looks at it.
"""
from __future__ import annotations

import os


def prune_unresolvable_path_entries() -> list[str]:
    """Remove PATH entries that raise on realpath. Returns what was dropped."""
    raw = os.environ.get("PATH")
    if not raw:
        return []

    kept: list[str] = []
    dropped: list[str] = []
    for entry in raw.split(os.pathsep):
        if not entry:
            continue
        try:
            os.path.realpath(entry)
        except OSError:
            dropped.append(entry)
        else:
            kept.append(entry)

    if dropped:
        os.environ["PATH"] = os.pathsep.join(kept)
    return dropped
