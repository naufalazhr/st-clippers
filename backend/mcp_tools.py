"""MCP tool surface for Sultan Clip.

What a tool must never return (playbook B.3): the AI provider API key, the MCP
token, or anything from outside this install's output directory. Clip files are
the user's own rendered work and are returned as absolute paths on purpose --
Telegram sends a local file in one call, whereas a URL forces the agent to
download and re-upload it.

Handlers are plain functions: the domain logic lives in this process, so there
is no bridge between the socket and these calls.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

# JSON-RPC / tool error codes.
INVALID_PARAMS = -32602
TOOL_FAILED = -32000
INTERNAL_ERROR = -32603

# Long-poll budget. The cap is what an agent will wait for a single tool call;
# rendering takes far longer, so a slow job returns a job_id to poll rather than
# holding the socket (playbook B.4).
DEFAULT_WAIT_SECONDS = 100
MAX_WAIT_SECONDS = 120
POLL_INTERVAL_SECONDS = 1.0

# Guardrails (playbook B.6). Rendering is CPU-bound and the pipeline already
# saturates the machine, so a second concurrent job makes both slower rather
# than finishing sooner.
MAX_CONCURRENT_JOBS = 1
MAX_JOBS_PER_HOUR = 6

# Cap on how much text a listing returns, so a long history cannot blow past
# the agent's context.
MAX_JOBS_LISTED = 20
MAX_LOG_LINES = 12


def _fail(code: int, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _ok(text: str, structured: Any) -> dict[str, Any]:
    """Agents differ in which they read, and a human reading the Telegram
    transcript needs the text."""
    return {"ok": {"content": [{"type": "text", "text": text}], "structuredContent": structured}}


def _err_message(err: Exception) -> str:
    return getattr(err, "message", None) or str(err) or err.__class__.__name__


def _api():
    """Imported lazily: api.py imports this module for its status endpoints."""
    import api

    return api


def clip_absolute_path(api_mod, clip) -> str | None:
    """Absolute path of a rendered clip, for Telegram to upload directly."""
    url = (clip.url or "").split("?")[0]
    prefix = "/outputs/"
    if not url.startswith(prefix):
        return None
    from urllib.parse import unquote

    relative = unquote(url[len(prefix):])
    path = (api_mod.OUTPUTS_DIR / relative).resolve()
    try:
        # Never hand back a path outside this install's output directory.
        path.relative_to(api_mod.OUTPUTS_DIR.resolve())
    except ValueError:
        return None
    return str(path) if path.is_file() else None


def _clip_payload(api_mod, clip) -> dict[str, Any]:
    return {
        "name": clip.name,
        "path": clip_absolute_path(api_mod, clip),
        "size_bytes": clip.size_bytes,
        "virality_score": getattr(clip, "virality_score", 0),
        "virality_reason": getattr(clip, "virality_reason", ""),
        "social_caption": clip.social_caption,
    }


def _job_summary(job) -> dict[str, Any]:
    request = job.request
    return {
        "job_id": job.id,
        "status": job.status,
        "source": request.url or request.source_file,
        "topic": getattr(request, "topic", "") or "",
        "clips_ready": len(job.clips),
        "clips_expected": job.clips_expected,
        "created_at": job.created_at,
        "error": job.error,
    }


def _job_detail(api_mod, job) -> dict[str, Any]:
    detail = _job_summary(job)
    detail["clips"] = [_clip_payload(api_mod, clip) for clip in job.clips]
    detail["recent_log"] = (job.logs or [])[-MAX_LOG_LINES:]
    return detail


# --- guardrails -------------------------------------------------------------

def _active_jobs(api_mod) -> list[Any]:
    with api_mod.jobs_lock:
        return [j for j in api_mod.jobs.values() if j.status in ("queued", "running")]


def _jobs_started_since(api_mod, cutoff_iso: str) -> int:
    with api_mod.jobs_lock:
        return sum(1 for j in api_mod.jobs.values() if (j.created_at or "") >= cutoff_iso)


def check_guardrails(api_mod) -> dict[str, Any] | None:
    """Returns a failure reply, or None when it is safe to start a job."""
    if len(_active_jobs(api_mod)) >= MAX_CONCURRENT_JOBS:
        return _fail(
            TOOL_FAILED,
            "Masih ada job yang sedang berjalan. Tunggu sampai selesai, lalu coba lagi. "
            "Gunakan get_job untuk memantau progresnya.",
        )
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    if _jobs_started_since(api_mod, cutoff) >= MAX_JOBS_PER_HOUR:
        return _fail(
            TOOL_FAILED,
            f"Batas {MAX_JOBS_PER_HOUR} job per jam sudah tercapai. "
            "Ini untuk mencegah render menumpuk. Coba lagi nanti.",
        )
    return None


def _clamp_wait(value: Any) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return DEFAULT_WAIT_SECONDS
    return max(0, min(MAX_WAIT_SECONDS, seconds))


def _wait_for_job(api_mod, job_id: str, wait_seconds: int):
    deadline = time.time() + wait_seconds
    while True:
        with api_mod.jobs_lock:
            job = api_mod.jobs.get(job_id)
        if job is None or job.status not in ("queued", "running"):
            return job
        if time.time() >= deadline:
            return job
        time.sleep(POLL_INTERVAL_SECONDS)


# --- handlers ---------------------------------------------------------------

def handle_list_jobs(args: dict[str, Any]) -> dict[str, Any]:
    api_mod = _api()
    with api_mod.jobs_lock:
        jobs = sorted(api_mod.jobs.values(), key=lambda j: j.created_at or "", reverse=True)
    jobs = jobs[:MAX_JOBS_LISTED]
    summaries = [_job_summary(j) for j in jobs]

    if not summaries:
        text = "Belum ada job. Gunakan create_clip_job untuk membuat klip dari sebuah video."
    else:
        lines = [
            f"- {s['job_id'][:8]} · {s['status']} · {s['clips_ready']} klip · {s['source'][:60]}"
            for s in summaries
        ]
        text = "Job terbaru:\n" + "\n".join(lines)
    return _ok(text, {"jobs": summaries})


def handle_get_job(args: dict[str, Any]) -> dict[str, Any]:
    api_mod = _api()
    job_id = args.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        return _fail(INVALID_PARAMS, "job_id is required")

    wait_seconds = _clamp_wait(args.get("wait_seconds", 0))
    with api_mod.jobs_lock:
        job = api_mod.jobs.get(job_id)
    if job is None:
        return _fail(INVALID_PARAMS, f"job tidak ditemukan: {job_id}")

    if wait_seconds and job.status in ("queued", "running"):
        job = _wait_for_job(api_mod, job_id, wait_seconds) or job

    detail = _job_detail(api_mod, job)
    if job.status == "completed":
        text = f"Job selesai dengan {len(job.clips)} klip."
        if job.clips:
            best = job.clips[0]
            text += (
                f" Klip teratas: \"{best.name}\" (skor viral "
                f"{getattr(best, 'virality_score', 0)})."
            )
    elif job.status == "failed":
        text = f"Job gagal: {job.error or 'tidak diketahui'}"
    else:
        text = (
            f"Job masih {job.status} ({len(job.clips)} dari "
            f"{job.clips_expected or '?'} klip siap). "
            "Panggil get_job lagi dengan wait_seconds untuk menunggu."
        )
    return _ok(text, detail)


def handle_list_clips(args: dict[str, Any]) -> dict[str, Any]:
    api_mod = _api()
    job_id = args.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        return _fail(INVALID_PARAMS, "job_id is required")
    with api_mod.jobs_lock:
        job = api_mod.jobs.get(job_id)
    if job is None:
        return _fail(INVALID_PARAMS, f"job tidak ditemukan: {job_id}")

    clips = [_clip_payload(api_mod, c) for c in job.clips]
    if not clips:
        text = f"Job {job_id[:8]} belum menghasilkan klip (status: {job.status})."
    else:
        lines = [
            f"{i + 1}. {c['name']} · skor {c['virality_score']} · {c['virality_reason'][:80]}"
            for i, c in enumerate(clips)
        ]
        text = "Klip (diurutkan dari skor viral tertinggi):\n" + "\n".join(lines)
    return _ok(text, {"job_id": job_id, "status": job.status, "clips": clips})


def handle_create_clip_job(args: dict[str, Any]) -> dict[str, Any]:
    api_mod = _api()

    url = (args.get("url") or "").strip()
    topic = (args.get("topic") or "").strip()

    # Missing input is a result, not an error (playbook B.7): an agent told what
    # is missing asks the user, whereas one told "invalid arguments" invents a
    # value. Checked before any side effect.
    if not url:
        return _ok(
            "Butuh URL video sebelum bisa membuat klip. Tanyakan ke pengguna:\n"
            "1. Link video (YouTube atau sejenisnya)\n"
            "2. Topik yang ingin disorot (opsional, tapi hasilnya jauh lebih relevan)",
            {"status": "needs_input", "missing": ["url"]},
        )

    blocked = check_guardrails(api_mod)
    if blocked is not None:
        return blocked

    request_fields: dict[str, Any] = {"url": url, "topic": topic}
    for key, cast in (
        ("top", int),
        ("min_duration", float),
        ("max_duration", float),
    ):
        if args.get(key) is not None:
            try:
                request_fields[key] = cast(args[key])
            except (TypeError, ValueError):
                return _fail(INVALID_PARAMS, f"{key} harus berupa angka")
    if args.get("crop_mode") is not None:
        request_fields["crop_mode"] = args["crop_mode"]
    if args.get("burn_subtitles") is not None:
        request_fields["burn_subtitles"] = bool(args["burn_subtitles"])

    try:
        job_request = api_mod.ClipJobRequest(**request_fields)
    except Exception as exc:
        return _fail(INVALID_PARAMS, f"parameter tidak valid: {_err_message(exc)}")

    try:
        job = api_mod.create_job(job_request)
    except Exception as exc:
        return _fail(TOOL_FAILED, f"gagal memulai job: {_err_message(exc)}")

    wait_seconds = _clamp_wait(args.get("wait_seconds", DEFAULT_WAIT_SECONDS))
    if wait_seconds:
        job = _wait_for_job(api_mod, job.id, wait_seconds) or job

    detail = _job_detail(api_mod, job)
    if job.status in ("queued", "running"):
        # Same shape as the finished reply plus status, so the agent needs only
        # one parser.
        text = (
            f"Job dimulai (id {job.id[:8]}). Render biasanya beberapa menit. "
            "Beri tahu pengguna bahwa prosesnya berjalan, lalu panggil get_job "
            "dengan wait_seconds untuk menunggu -- jangan diam saja."
        )
    elif job.status == "failed":
        text = f"Job gagal: {job.error or 'tidak diketahui'}"
    else:
        text = f"Job selesai dengan {len(job.clips)} klip."
    return _ok(text, detail)


# --- registry ---------------------------------------------------------------

_FRESHNESS = (
    "Results are read live at call time and go stale as soon as the user changes "
    "anything in the app - always call this again before answering, never reuse "
    "an earlier result."
)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_jobs",
        "description": (
            "List the user's recent clipping jobs with status and how many clips each "
            "produced. Call this first when the user asks what they have, which video "
            "was processed, or to pick a job to look at. " + _FRESHNESS
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_job",
        "description": (
            "Get one job's status, its finished clips (with virality score, the reason "
            "it could travel, and an absolute file path), and the last lines of its log. "
            "Use wait_seconds to block until the job finishes instead of polling in a "
            "loop; if it is still running when the wait ends you get the same shape back "
            "with status 'running', so keep calling and tell the user what is happening "
            "between calls. " + _FRESHNESS
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job id from list_jobs or create_clip_job."},
                "wait_seconds": {
                    "type": "integer",
                    "description": (
                        f"Block up to this many seconds for the job to finish "
                        f"(0-{MAX_WAIT_SECONDS}, default 0 = answer immediately)."
                    ),
                },
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_clips",
        "description": (
            "List the finished clips of a job, ranked by virality score, each with an "
            "absolute file path. Send those files to the user directly rather than a "
            "link. Call this before offering to re-render anything: a clip that already "
            "exists costs nothing to send and the user already waited for it. " + _FRESHNESS
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"job_id": {"type": "string", "description": "Job id to read clips from."}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "create_clip_job",
        "description": (
            "Turn a video into short vertical clips. Ask the user for the video link and "
            "the topic they want highlighted BEFORE calling this - the topic strongly "
            "changes which moments are chosen, and clipping the wrong part wastes several "
            "minutes of rendering. Rendering is slow: this returns status 'running' with a "
            "job_id, and you must then poll get_job and keep the user informed rather than "
            "going silent. Only one job runs at a time."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Video URL, e.g. a YouTube link."},
                "topic": {
                    "type": "string",
                    "description": (
                        "What the user wants highlighted. Clips covering this are ranked "
                        "far above the rest. Ask the user; do not invent it."
                    ),
                },
                "top": {"type": "integer", "description": "How many clips to produce (1-50)."},
                "min_duration": {"type": "number", "description": "Minimum clip length in seconds."},
                "max_duration": {"type": "number", "description": "Maximum clip length in seconds."},
                "crop_mode": {
                    "type": "string",
                    "enum": ["center", "person", "streamer", "pillarbox", "split"],
                    "description": "Vertical framing. 'split' suits screen recordings with a webcam.",
                },
                "burn_subtitles": {"type": "boolean", "description": "Burn captions into the video."},
                "wait_seconds": {
                    "type": "integer",
                    "description": (
                        f"Block up to this many seconds before returning "
                        f"(0-{MAX_WAIT_SECONDS}, default {DEFAULT_WAIT_SECONDS})."
                    ),
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    },
]

HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "list_jobs": handle_list_jobs,
    "get_job": handle_get_job,
    "list_clips": handle_list_clips,
    "create_clip_job": handle_create_clip_job,
}


def dispatch(method: str, params: Any) -> dict[str, Any]:
    """Single entry point. Never raises: the caller must always get one reply."""
    try:
        if method == "tools/list":
            return {"ok": {"tools": TOOL_DEFINITIONS}}
        if method == "tools/call":
            params = params if isinstance(params, dict) else {}
            name = params.get("name")
            args = params.get("arguments")
            handler = HANDLERS.get(name) if isinstance(name, str) else None
            if handler is None:
                return _fail(INVALID_PARAMS, f"unknown tool: {name}")
            return handler(args if isinstance(args, dict) else {})
        return _fail(-32601, f"unsupported method: {method}")
    except Exception as exc:
        return _fail(INTERNAL_ERROR, _err_message(exc))
