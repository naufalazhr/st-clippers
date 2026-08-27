"""Entry point for PyInstaller sidecar — uvicorn API, clipper CLI, or multiproc child."""
from __future__ import annotations

import argparse
import os
import sys

# socket.getaddrinfo() encodes every hostname with the "idna" codec, so a frozen
# build that omits these dies on the first network call with
# "unknown encoding: idna". Importing them here (not only via the spec's
# hiddenimports) guarantees PyInstaller's analysis bundles them and registers
# the codecs before anything reaches the network.
import encodings.idna  # noqa: F401
import encodings.punycode  # noqa: F401


def _force_utf8_streams() -> None:
    """Make stdout/stderr UTF-8 so non-Latin-1 text cannot kill the process.

    A frozen build on Windows gets cp1252 streams, so printing anything the
    transcript or the LLM produced outside that range (a non-breaking hyphen was
    enough) raised UnicodeEncodeError and took the whole pipeline down.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


_force_utf8_streams()


def _run_multiprocessing_child() -> bool:
    if not getattr(sys, "frozen", False):
        return False
    if "-c" not in sys.argv:
        return False
    try:
        idx = sys.argv.index("-c")
        code = sys.argv[idx + 1]
    except (ValueError, IndexError):
        return False
    sys.argv = [sys.argv[0]]
    exec(code, {"__name__": "__main__"})
    return True


def main() -> None:
    if _run_multiprocessing_child():
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--clipper":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        try:
            import multiprocessing

            multiprocessing.freeze_support()
        except Exception:
            pass
        from clipper import main as clipper_main

        raise SystemExit(clipper_main())

    parser = argparse.ArgumentParser(description="Sultan Clip backend server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SULTANCLIP_PORT", "8010")),
        help="Port to listen on (default: 8010, env: SULTANCLIP_PORT)",
    )
    args = parser.parse_args()

    from api import app
    import uvicorn

    # Announce readiness from the startup hook. Printing it before importing api
    # fired the signal seconds early -- the heavy imports below had not run and
    # nothing was listening yet, so anything trusting it raced a dead socket.
    app.router.on_startup.append(lambda: print("SULTANCLIP_READY", flush=True))

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    try:
        import multiprocessing

        multiprocessing.freeze_support()
    except Exception:
        pass
    main()
