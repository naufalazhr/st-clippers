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

import threading
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


# --- styling surface --------------------------------------------------------
# The same options the app's own controls offer, so an agent can do what a user
# can do in the UI. Two deliberate exclusions:
#   * caption text/segment editing -- rewriting what was transcribed is the
#     user's call, not the agent's;
#   * ai_api_key and anything else secret (playbook B.3).
STYLE_PROPERTIES: dict[str, Any] = {
    "crop_mode": {
        "type": "string",
        "enum": ["center", "person", "streamer", "pillarbox", "split"],
        "description": (
            "Vertical framing. 'center' crops the middle, 'person' tracks the "
            "speaker, 'streamer' stacks a webcam over the screen, 'pillarbox' "
            "fits the whole frame over a blurred backdrop, 'split' puts a face "
            "panel above the activity view."
        ),
    },
    "cam_corner": {
        "type": "string",
        "enum": ["auto", "br", "bl", "tr", "tl"],
        "description": "Which corner the webcam sits in, for 'streamer'/'split'. 'auto' detects it.",
    },
    "burn_subtitles": {"type": "boolean", "description": "Burn captions into the video."},
    "caption_style": {
        "type": "string",
        "enum": ["classic", "bold", "boxed", "highlight", "shadow"],
        "description": (
            "Caption look. 'boxed' draws a solid plate behind the text, "
            "'highlight' a translucent one, 'shadow' a drop shadow."
        ),
    },
    "caption_font": {
        "type": "string",
        "enum": ["DejaVu Sans", "DejaVu Serif", "Liberation Sans", "Liberation Serif", "Noto Sans"],
        "description": "Caption typeface. Only these are bundled; anything else is rejected.",
    },
    "caption_font_size": {
        "type": "integer",
        "description": "Caption size, 6-120. Around 30 is readable on a phone.",
    },
    "caption_position": {
        "type": "string",
        "enum": ["center", "bottom"],
        "description": "Where captions sit in the 9:16 frame.",
    },
    "caption_color": {"type": "string", "description": "Caption fill colour as hex, e.g. #FFFFFF."},
    "caption_outline": {"type": "number", "description": "Caption outline width, 0-8."},
    "caption_outline_color": {
        "type": "string",
        "description": "Outline colour as hex. For 'boxed'/'highlight' this is the box colour.",
    },
    "caption_box_opacity": {
        "type": "integer",
        "description": (
            "Opacity 0-100 of the box behind 'boxed'/'highlight' captions. "
            "Omit to use the preset default (boxed solid, highlight translucent)."
        ),
    },
    "transition": {
        "type": "string",
        "enum": ["none", "fade", "fadeblack", "fadewhite"],
        "description": "Transition at the clip boundaries.",
    },
    "watermark_text": {"type": "string", "description": "Text watermark, e.g. an @handle."},
    "watermark_position": {
        "type": "string",
        "enum": [
            "top-left", "top-center", "top-right",
            "center-left", "center", "center-right",
            "bottom-left", "bottom-center", "bottom-right",
        ],
        "description": "Where the watermark sits.",
    },
    "watermark_opacity": {"type": "number", "description": "Watermark opacity, 0.0-1.0."},
    "watermark_scale": {"type": "integer", "description": "Watermark size as a percentage, 1-500."},
    "watermark_color": {"type": "string", "description": "Watermark colour as hex."},
    "watermark_font_family": {
        "type": "string",
        "enum": ["DejaVu Sans", "DejaVu Serif", "Liberation Sans", "Liberation Serif", "Noto Sans"],
        "description": "Watermark typeface.",
    },
}

# Options that only make sense when first creating clips, not when restyling one.
CREATION_PROPERTIES: dict[str, Any] = {
    "top": {"type": "integer", "description": "How many clips to produce, 1-50."},
    "min_duration": {"type": "number", "description": "Shortest clip in seconds, 5-600."},
    "max_duration": {"type": "number", "description": "Longest clip in seconds, 10-600."},
    "language": {"type": "string", "description": "Spoken language code, e.g. 'id' or 'en'."},
    "analyze_seconds": {
        "type": "number",
        "description": "Only analyse the first N seconds. Omit to analyse the whole video.",
    },
    "required_hashtags": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Hashtags to include in every generated social caption.",
    },
}

# Applied on a restyle. Caption text is deliberately absent.
RESTYLE_FIELDS = tuple(STYLE_PROPERTIES)


def _collect_style_args(args: dict[str, Any], allowed: tuple[str, ...]) -> dict[str, Any]:
    """Pick out the styling arguments the caller actually supplied."""
    return {key: args[key] for key in allowed if args.get(key) is not None}


def _validation_message(exc: Exception) -> str:
    """Turn a Pydantic error into something an agent can act on."""
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return _err_message(exc)
    parts = []
    for item in errors()[:4]:
        field = ".".join(str(p) for p in item.get("loc", ())) or "argument"
        parts.append(f"{field}: {item.get('msg', 'tidak valid')}")
    return "; ".join(parts) or _err_message(exc)


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
    request_fields.update(_collect_style_args(args, tuple(STYLE_PROPERTIES)))
    request_fields.update(_collect_style_args(args, tuple(CREATION_PROPERTIES)))

    try:
        # Pydantic owns the ranges and enums, so an agent gets exactly the
        # validation the app's own form does.
        job_request = api_mod.ClipJobRequest(**request_fields)
    except Exception as exc:
        return _fail(INVALID_PARAMS, f"parameter tidak valid: {_validation_message(exc)}")

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


def handle_get_style_options(args: dict[str, Any]) -> dict[str, Any]:
    """Every option the app's controls offer, with allowed values and defaults.

    Without this an agent guesses font names and framing modes, and guessing
    costs a whole render to find out it was wrong.
    """
    api_mod = _api()
    defaults = api_mod.ClipJobRequest(url="https://example.invalid")

    options: dict[str, Any] = {}
    for name, spec in {**STYLE_PROPERTIES, **CREATION_PROPERTIES}.items():
        entry: dict[str, Any] = {"description": spec["description"]}
        if "enum" in spec:
            entry["allowed"] = spec["enum"]
        current = getattr(defaults, name, None)
        if current is not None:
            entry["default"] = current
        options[name] = entry

    lines = [
        "Opsi yang bisa diatur (sama seperti di aplikasi):",
        "- Framing: " + ", ".join(STYLE_PROPERTIES["crop_mode"]["enum"]),
        "- Style caption: " + ", ".join(STYLE_PROPERTIES["caption_style"]["enum"]),
        "- Font: " + ", ".join(STYLE_PROPERTIES["caption_font"]["enum"]),
        "- Posisi caption: " + ", ".join(STYLE_PROPERTIES["caption_position"]["enum"]),
        "- Transisi: " + ", ".join(STYLE_PROPERTIES["transition"]["enum"]),
        "Pakai nilai persis seperti di atas; nilai lain akan ditolak.",
    ]
    return _ok("\n".join(lines), {"options": options})


def handle_restyle_clip(args: dict[str, Any]) -> dict[str, Any]:
    """Re-render one existing clip with different styling.

    The app's Edit Caption dialog can also rewrite the transcribed text; that is
    deliberately not exposed. This changes only how the clip looks and leaves
    what it says untouched.
    """
    api_mod = _api()

    job_id = args.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        return _fail(INVALID_PARAMS, "job_id is required")
    clip_index = args.get("clip_index")
    if not isinstance(clip_index, int) or isinstance(clip_index, bool):
        return _fail(INVALID_PARAMS, "clip_index harus berupa angka (lihat list_clips)")

    with api_mod.jobs_lock:
        job = api_mod.jobs.get(job_id)
    if job is None:
        return _fail(INVALID_PARAMS, f"job tidak ditemukan: {job_id}")
    if not job.work_dir:
        return _fail(TOOL_FAILED, "Job ini tidak punya sumber yang bisa dirender ulang.")

    candidate = next((c for c in job.candidates if c.index == clip_index), None)
    if candidate is None:
        available = ", ".join(str(c.index) for c in job.candidates) or "tidak ada"
        return _fail(INVALID_PARAMS, f"klip {clip_index} tidak ada. Tersedia: {available}")

    changes = _collect_style_args(args, RESTYLE_FIELDS)
    if not changes:
        # Saying so beats spending minutes of render on a byte-identical clip.
        return _ok(
            "Tidak ada perubahan gaya yang diminta, jadi tidak ada yang dirender ulang. "
            "Sebutkan misalnya caption_style, caption_font_size, atau transition. "
            "Panggil get_style_options untuk melihat pilihannya.",
            {"status": "no_changes", "clip_index": clip_index},
        )

    if len(_active_jobs(api_mod)) >= MAX_CONCURRENT_JOBS:
        return _fail(
            TOOL_FAILED,
            "Masih ada render yang berjalan. Tunggu selesai sebelum mengubah gaya klip.",
        )

    try:
        # start/end come from the stored candidate: the agent asks to restyle a
        # clip, not to recut a timespan it would otherwise have to know.
        recut = api_mod.RecutRequest(
            index=clip_index, start=candidate.start, end=candidate.end, **changes
        )
    except Exception as exc:
        return _fail(INVALID_PARAMS, f"parameter tidak valid: {_validation_message(exc)}")

    try:
        api_mod.validate_recut(job, clip_index, candidate.start, candidate.end, None)
    except ValueError as exc:
        return _fail(TOOL_FAILED, f"tidak bisa render ulang: {_err_message(exc)}")

    api_mod.set_job(job_id, status="running", recut_index=clip_index, recut_error=None)
    threading.Thread(target=api_mod.run_recut, args=(job_id, recut), daemon=True).start()

    wait_seconds = _clamp_wait(args.get("wait_seconds", DEFAULT_WAIT_SECONDS))
    if wait_seconds:
        _wait_for_job(api_mod, job_id, wait_seconds)

    with api_mod.jobs_lock:
        job = api_mod.jobs.get(job_id)
    if job is not None and job.recut_error:
        return _fail(TOOL_FAILED, f"render ulang gagal: {job.recut_error}")

    detail = _job_detail(api_mod, job) if job else {}
    detail["restyled_clip_index"] = clip_index
    detail["applied"] = changes
    applied = ", ".join(f"{k}={v}" for k, v in changes.items())
    if job is not None and job.status in ("queued", "running"):
        text = (
            f"Klip {clip_index} sedang dirender ulang ({applied}). "
            "Panggil get_job untuk menunggu, dan kabari pengguna sambil menunggu."
        )
    else:
        text = f"Klip {clip_index} selesai dirender ulang ({applied})."
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
            "going silent. Only one job runs at a time. Every look-and-feel option "
            "the app offers can be set here - call get_style_options first "
            "rather than guessing a font or framing name. Clips started from "
            "here are scored heuristically: AI scoring needs the provider key "
            "configured in the app itself."
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
                **STYLE_PROPERTIES,
                **CREATION_PROPERTIES,
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
    {
        "name": "get_style_options",
        "description": (
            "List every look-and-feel option the app offers - framing modes, caption "
            "styles, fonts, positions, transitions and watermark placement - with the "
            "values each one accepts and its default. Call this before create_clip_job "
            "or restyle_clip whenever the user describes an appearance in their own "
            "words, so you map it to a real value instead of guessing one. "
            + _FRESHNESS
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "restyle_clip",
        "description": (
            "Re-render one existing clip with different styling: caption style, font, "
            "size, colour, position, box opacity, framing, transition or watermark. Use "
            "this when the user likes a clip's content but not how it looks - it reuses "
            "the existing transcript and re-renders only that clip, leaving the others "
            "alone. It cannot change the caption wording; the user edits text in the "
            "app. Rendering takes a few minutes, so poll get_job afterwards and keep "
            "the user informed. Call get_style_options first if unsure of a value."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job the clip belongs to."},
                "clip_index": {
                    "type": "integer",
                    "description": "Which clip to restyle, from list_clips or get_job.",
                },
                **STYLE_PROPERTIES,
                "wait_seconds": {
                    "type": "integer",
                    "description": (
                        f"Block up to this many seconds before returning "
                        f"(0-{MAX_WAIT_SECONDS}, default {DEFAULT_WAIT_SECONDS})."
                    ),
                },
            },
            "required": ["job_id", "clip_index"],
            "additionalProperties": False,
        },
    },
]

HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "list_jobs": handle_list_jobs,
    "get_job": handle_get_job,
    "list_clips": handle_list_clips,
    "get_style_options": handle_get_style_options,
    "create_clip_job": handle_create_clip_job,
    "restyle_clip": handle_restyle_clip,
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
