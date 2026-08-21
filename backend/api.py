from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import struct
import threading
import time
import traceback
import uuid
import wave
from math import ceil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urlparse

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from yt_dlp import YoutubeDL


BASE_DIR = Path(__file__).resolve().parent


def resolve_data_dir() -> Path:
    if env := os.environ.get("SULTANCLIP_DATA_DIR"):
        path = Path(env)
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "SultanClip"
    elif sys.platform == "win32":
        path = Path(os.environ.get("APPDATA", str(BASE_DIR))) / "SultanClip"
    else:
        path = BASE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


OUTPUTS_DIR = resolve_data_dir() / "outputs"
UPLOADS_DIR = resolve_data_dir() / "uploads"
JOBS_PATH = resolve_data_dir() / "jobs.json"
ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
SECONDS_PER_TARGET_CLIP = 360
MIN_AUTO_CLIPS = 2
MAX_AUTO_CLIPS = 8
FULL_ANALYSIS_LIMIT_SECONDS = 30 * 60
LONG_VIDEO_ANALYSIS_RATIO = 0.55
MAX_AUTO_ANALYSIS_SECONDS = 60 * 60
CLIP_BUDGET_RATIO = 0.8


class ClipJobRequest(BaseModel):
    url: str = ""
    source_file: str = ""
    top: int | None = Field(default=None, ge=1, le=50)
    min_duration: float = Field(default=35, ge=5, le=600)
    max_duration: float = Field(default=180, ge=10, le=600)
    model: str = "Systran/faster-whisper-small"
    language: str = "id"
    analyze_seconds: float | None = Field(default=None, ge=10, le=7200)
    burn_subtitles: bool = True
    crop_mode: Literal["center", "person", "streamer"] = "center"
    cam_corner: Literal["auto", "br", "bl", "tr", "tl"] = "auto"
    caption_font_size: int = Field(default=30, ge=6, le=120)
    caption_position: Literal["center", "bottom"] = "center"
    caption_color: str = "#FFFFFF"
    caption_font: Literal[
        "DejaVu Sans", "DejaVu Serif", "Liberation Sans", "Liberation Serif", "Noto Sans"
    ] = "DejaVu Sans"
    caption_outline: float = Field(default=2.0, ge=0, le=8)
    caption_outline_color: str = "#000000"
    required_hashtags: list[str] = Field(default_factory=list)
    ai_enabled: bool = False
    ai_base_url: str = ""
    ai_model: str = ""
    ai_api_key: str = ""
    name: str = ""
    watermark_text: str | None = None
    watermark_image: str | None = None
    watermark_position: str = "bottom-right"
    watermark_opacity: float = Field(default=0.8, ge=0.0, le=1.0)
    watermark_scale: int = Field(default=100, ge=1, le=500)
    watermark_font_family: str | None = None
    watermark_color: str | None = None
    watermark_margin_x: int = Field(default=20, ge=0)
    watermark_margin_y: int = Field(default=20, ge=0)

    @field_validator("caption_color", "caption_outline_color")
    @classmethod
    def _validate_hex_color(cls, value: str) -> str:
        candidate = value.strip()
        if not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", candidate):
            raise ValueError("color must be a hex value like #FFFFFF")
        return candidate.upper()


class ClipCandidate(BaseModel):
    index: int
    start: float
    end: float
    duration: float
    score: int
    title: str
    reason: str
    text: str


class TranscriptSegmentOut(BaseModel):
    start: float
    end: float
    text: str


class TimelineData(BaseModel):
    source_url: str
    duration: float
    segments: list[TranscriptSegmentOut]
    candidates: list[ClipCandidate]
    peaks: list[int] = []


class RecutRequest(BaseModel):
    index: int
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    segments: list[dict] | None = Field(default=None)
    caption_font_size: int | None = None
    caption_position: str | None = None
    caption_color: str | None = None
    caption_font: str | None = None
    caption_outline: int | None = None
    caption_outline_color: str | None = None
    watermark_text: str | None = None
    watermark_image: str | None = None
    watermark_position: str = "bottom-right"
    watermark_opacity: float = Field(default=0.8, ge=0.0, le=1.0)
    watermark_scale: int = Field(default=100, ge=1, le=500)
    watermark_font_family: str | None = None
    watermark_color: str | None = None
    watermark_margin_x: int = Field(default=20, ge=0)
    watermark_margin_y: int = Field(default=20, ge=0)


class ClipFile(BaseModel):
    name: str
    url: str
    size_bytes: int
    thumbnail_url: str | None = None
    thumbnail_prompt: str | None = None
    social_caption: str | None = None


class ClipJob(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    request: ClipJobRequest
    created_at: str
    updated_at: str
    logs: list[str] = []
    clips: list[ClipFile] = []
    candidates: list[ClipCandidate] = []
    error: str | None = None
    work_dir: str | None = None


# The packaged webview origin differs per platform:
#   macOS   -> tauri://localhost
#   Windows -> http://tauri.localhost (https://tauri.localhost when useHttpsScheme is on)
#   Linux   -> http://tauri.localhost
# Every origin has to be allowed, otherwise the webview blocks the response and
# fetch() rejects with "Failed to fetch".
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]
# Dev servers do not always land on port 3000; allow any loopback origin.
ALLOWED_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

app = FastAPI(title="Sultan Clip API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")


def resolve_upload_path(token: str) -> Path | None:
    # token is just the stored file name; keep it confined to UPLOADS_DIR.
    name = Path(token).name
    if not name:
        return None
    candidate = (UPLOADS_DIR / name).resolve()
    root = UPLOADS_DIR.resolve()
    if root != candidate.parent or not candidate.is_file():
        return None
    return candidate

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_jobs() -> dict[str, ClipJob]:
    if not JOBS_PATH.exists():
        return {}

    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    loaded: dict[str, ClipJob] = {}
    for item in payload:
        job = ClipJob(**item)
        if job.status in {"queued", "running"}:
            data = job.model_dump()
            data["status"] = "failed"
            data["updated_at"] = now_iso()
            data["error"] = "Backend restarted before this job finished"
            job = ClipJob(**data)
        loaded[job.id] = job
    return loaded


def save_jobs_unlocked() -> None:
    jobs_list = sorted(jobs.values(), key=lambda job: job.created_at, reverse=True)
    payload = [job.model_dump() for job in jobs_list]
    data = json.dumps(payload, indent=2, ensure_ascii=False)
    try:
        temp_path = JOBS_PATH.with_suffix(".json.tmp")
        temp_path.write_text(data, encoding="utf-8")
        temp_path.replace(JOBS_PATH)
    except OSError:
        # JOBS_PATH may be a bind-mounted file; atomic rename over it fails
        # with Errno 16. Fall back to in-place write (single writer under lock).
        JOBS_PATH.write_text(data, encoding="utf-8")


def clear_outputs_dir() -> int:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    root = OUTPUTS_DIR.resolve()
    removed = 0
    for item in OUTPUTS_DIR.iterdir():
        resolved = item.resolve()
        if root not in resolved.parents:
            raise RuntimeError(f"Refusing to delete path outside outputs: {resolved}")

        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
        removed += 1
    return removed


def clear_uploads_dir() -> int:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    for item in UPLOADS_DIR.iterdir():
        if item.is_file():
            item.unlink()
            removed += 1
    return removed


jobs: dict[str, ClipJob] = load_jobs()
jobs_lock = threading.Lock()
job_secrets: dict[str, str] = {}


def clip_url(path: Path) -> str:
    relative = path.resolve().relative_to(OUTPUTS_DIR.resolve()).as_posix()
    return "/outputs/" + quote(relative)


def clip_file_from_path(path: Path) -> ClipFile:
    thumb_path = path.with_name(f"{path.stem}_thumb.jpg")
    prompt_path = path.with_name(f"{path.stem}_thumb.txt")
    caption_path = path.with_name(f"{path.stem}_caption.txt")
    return ClipFile(
        name=path.name,
        url=clip_url(path),
        size_bytes=path.stat().st_size,
        thumbnail_url=clip_url(thumb_path) if thumb_path.exists() else None,
        thumbnail_prompt=prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else None,
        social_caption=caption_path.read_text(encoding="utf-8") if caption_path.exists() else None,
    )


def discover_clips(started_at: float) -> list[ClipFile]:
    clips: list[ClipFile] = []
    for path in OUTPUTS_DIR.rglob("clips/*.mp4"):
        if path.stat().st_mtime + 1 < started_at:
            continue
        clips.append(clip_file_from_path(path))
    clips.sort(key=lambda item: item.name)
    return clips


def discover_candidates(started_at: float) -> list[ClipCandidate]:
    candidate_files = [
        path
        for path in OUTPUTS_DIR.rglob("candidates*.json")
        if path.stat().st_mtime + 1 >= started_at
    ]
    if not candidate_files:
        return []

    latest = max(candidate_files, key=lambda path: path.stat().st_mtime)
    payload = json.loads(latest.read_text(encoding="utf-8"))
    return [ClipCandidate(**item) for item in payload]


def discover_work_dir(started_at: float) -> str | None:
    candidate_files = [
        path
        for path in OUTPUTS_DIR.rglob("candidates*.json")
        if path.stat().st_mtime + 1 >= started_at
    ]
    if not candidate_files:
        return None
    latest = max(candidate_files, key=lambda p: p.stat().st_mtime)
    parent = latest.parent.resolve()
    return parent.relative_to(OUTPUTS_DIR.resolve()).as_posix()


def recut_clip(
    job: ClipJob,
    index: int,
    start: float,
    end: float,
    override_segments: list[dict] | None = None,
    recut_request: "RecutRequest | None" = None,
) -> tuple[ClipFile, ClipCandidate]:
    from clipper import ClipCandidate as ClipCandidateDC, TranscriptSegment as TranscriptSegmentDC
    from clipper import segments_for_clip, CaptionStyle, AIConfig, export_clip, WatermarkStyle

    req = job.request
    rr = recut_request
    work_dir = OUTPUTS_DIR / job.work_dir
    source = next(work_dir.glob("source.*"), None)
    if not source:
        raise ValueError("source not available")

    transcript_files = sorted(work_dir.glob("transcript*.json"), key=lambda p: p.stat().st_mtime)
    if not transcript_files:
        raise ValueError("no transcript")
    rows = json.loads(transcript_files[-1].read_text(encoding="utf-8"))
    segments = [TranscriptSegmentDC(**s) for s in rows]

    if override_segments is not None and len(override_segments) == 0:
        raise ValueError("segments must not be empty")

    duration = probe_media_duration(source) or max((s.end for s in segments), default=0)

    if start >= end:
        raise ValueError("start must be before end")
    if end > duration:
        raise ValueError("end exceeds video duration")

    cand = next((c for c in job.candidates if c.index == index), None)
    if cand is None:
        raise ValueError("candidate not found")

    dc_cand = ClipCandidateDC(
        index=index,
        start=start,
        end=end,
        duration=end - start,
        score=cand.score,
        title=cand.title,
        reason=cand.reason,
        text=cand.text,
    )

    if override_segments is not None and len(override_segments) == 0:
        raise ValueError("segments must not be empty")

    if override_segments is not None:
        clip_segments = [
            TranscriptSegmentDC(start=s["start"], end=s["end"], text=s["text"])
            for s in override_segments
        ]
        (work_dir / "transcript_edited.json").write_text(
            json.dumps(override_segments, ensure_ascii=False), encoding="utf-8"
        )
    else:
        clip_segments = segments_for_clip(segments, dc_cand)

    def _pick(override, fallback):
        return override if override is not None else fallback

    caption = CaptionStyle(
        font_size=_pick(rr.caption_font_size if rr else None, req.caption_font_size),
        position=_pick(rr.caption_position if rr else None, req.caption_position),
        color=_pick(rr.caption_color if rr else None, req.caption_color),
        font_family=_pick(rr.caption_font if rr else None, req.caption_font),
        outline_width=_pick(rr.caption_outline if rr else None, req.caption_outline),
        outline_color=_pick(rr.caption_outline_color if rr else None, req.caption_outline_color),
    )
    ai = AIConfig(enabled=False)

    wm: WatermarkStyle | None = None
    wm_text = _pick(rr.watermark_text if rr else None, req.watermark_text)
    wm_image = _pick(rr.watermark_image if rr else None, req.watermark_image)
    if wm_text or wm_image:
        wm_img_path = None
        if wm_image:
            wm_img_path = (OUTPUTS_DIR / job.work_dir / wm_image).resolve()
        wm = WatermarkStyle(
            text=wm_text,
            image_path=wm_img_path,
            position=_pick(rr.watermark_position if rr else None, req.watermark_position),
            opacity=_pick(rr.watermark_opacity if rr else None, req.watermark_opacity),
            scale=_pick(rr.watermark_scale if rr else None, req.watermark_scale),
            font_family=_pick(rr.watermark_font_family if rr else None, req.watermark_font_family),
            color=_pick(rr.watermark_color if rr else None, req.watermark_color),
            margin_x=_pick(rr.watermark_margin_x if rr else None, req.watermark_margin_x),
            margin_y=_pick(rr.watermark_margin_y if rr else None, req.watermark_margin_y),
        )

    out_path = export_clip(
        video_path=source,
        clip=dc_cand,
        clip_segments=clip_segments,
        clips_dir=work_dir / "clips",
        burn_subtitles=req.burn_subtitles,
        crop_mode=req.crop_mode,
        caption=caption,
        ai_config=ai,
        cam_corner=req.cam_corner,
        required_hashtags=req.required_hashtags,
        watermark=wm,
    )

    py_cand = ClipCandidate(
        index=index, start=start, end=end, duration=end - start,
        score=cand.score, title=cand.title, reason=cand.reason, text=cand.text,
    )
    return clip_file_from_path(out_path), py_cand


def set_job(job_id: str, **updates) -> None:
    with jobs_lock:
        job = jobs[job_id]
        data = job.model_dump()
        data.update(updates)
        data["updated_at"] = now_iso()
        jobs[job_id] = ClipJob(**data)
        save_jobs_unlocked()


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def fetch_video_duration(url: str) -> float | None:
    from clipper import _ydl_base_opts

    ydl_opts = {
        **_ydl_base_opts(),
        "skip_download": True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:  # noqa: BROAD_EXCEPT_OK — probe endpoint soft-fails
        return None

    duration = info.get("duration") if isinstance(info, dict) else None
    return float(duration) if duration else None


def probe_media_duration(path: Path) -> float | None:
    try:
        import cv2
    except Exception:
        return None
    capture = cv2.VideoCapture(str(path.resolve()))
    if not capture.isOpened():
        return None
    fps = capture.get(cv2.CAP_PROP_FPS)
    frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
    capture.release()
    if fps and frames and fps > 0:
        return float(frames) / float(fps)
    return None


def max_clips_for_duration(duration: float | None, min_duration: float) -> int | None:
    # Guarantee target clips can fit without overlap inside 80% of the video.
    if not duration or min_duration <= 0:
        return None
    return max(1, int((duration * CLIP_BUDGET_RATIO) // min_duration))


def choose_auto_top(duration: float | None) -> int:
    if not duration:
        return MIN_AUTO_CLIPS + 3
    return clamp(ceil(duration / SECONDS_PER_TARGET_CLIP), MIN_AUTO_CLIPS, MAX_AUTO_CLIPS)


def choose_auto_analyze_seconds(duration: float | None) -> float | None:
    if not duration or duration <= FULL_ANALYSIS_LIMIT_SECONDS:
        return None
    return min(MAX_AUTO_ANALYSIS_SECONDS, max(FULL_ANALYSIS_LIMIT_SECONDS, duration * LONG_VIDEO_ANALYSIS_RATIO))


def default_job_name(url: str, has_upload: bool) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    if has_upload or not url:
        return f"Upload {stamp}" if has_upload else f"Clip {stamp}"
    host = urlparse(url).hostname
    return f"{host} {stamp}" if host else f"Clip {stamp}"


def normalize_job_request(request: ClipJobRequest) -> ClipJobRequest:
    if request.source_file:
        duration = probe_media_duration(Path(request.source_file))
    else:
        duration = fetch_video_duration(request.url)
    data = request.model_dump()

    if request.top is None:
        data["top"] = choose_auto_top(duration)

    # Enforce: min_duration * target_clips <= 80% of the video length.
    budget_cap = max_clips_for_duration(duration, request.min_duration)
    if budget_cap is not None and data["top"] is not None:
        data["top"] = max(1, min(int(data["top"]), budget_cap))

    if request.analyze_seconds is None:
        data["analyze_seconds"] = choose_auto_analyze_seconds(duration)

    return ClipJobRequest(**data)


def build_clipper_command(request: ClipJobRequest) -> list[str]:
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--clipper"]
    else:
        command = [sys.executable, "clipper.py"]
    if request.source_file:
        command.extend(["--source-file", request.source_file])
    else:
        command.append(request.url)
    command.extend(
        [
            "--top",
            str(request.top or choose_auto_top(None)),
            "--min",
            str(request.min_duration),
            "--max",
            str(request.max_duration),
            "--model",
            request.model,
            "--language",
            request.language,
        ]
    )

    if request.analyze_seconds:
        command.extend(["--analyze-seconds", str(request.analyze_seconds)])
    if not request.burn_subtitles:
        command.append("--no-burn-subtitles")
    command.extend(["--crop-mode", request.crop_mode])
    command.extend(["--cam-corner", request.cam_corner])
    command.extend(["--caption-font-size", str(request.caption_font_size)])
    command.extend(["--caption-position", request.caption_position])
    command.extend(["--caption-color", request.caption_color])
    command.extend(["--caption-font", request.caption_font])
    command.extend(["--caption-outline", str(request.caption_outline)])
    command.extend(["--caption-outline-color", request.caption_outline_color])
    if request.required_hashtags:
        cleaned = [tag.strip().lstrip("#") for tag in request.required_hashtags if tag.strip()]
        if cleaned:
            command.extend(["--required-hashtags", ",".join(cleaned)])

    if request.ai_enabled:
        command.append("--ai-enabled")
        if request.ai_base_url:
            command.extend(["--ai-base-url", request.ai_base_url])
        if request.ai_model:
            command.extend(["--ai-model", request.ai_model])
        if request.ai_api_key:
            command.extend(["--ai-api-key", request.ai_api_key])

    if request.watermark_text:
        command.extend(["--watermark-text", request.watermark_text])
    if request.watermark_image:
        abs_path = str((OUTPUTS_DIR / request.watermark_image).resolve())
        command.extend(["--watermark-image", abs_path])
    if request.watermark_text or request.watermark_image:
        command.extend(["--watermark-position", request.watermark_position])
        command.extend(["--watermark-opacity", str(request.watermark_opacity)])
        command.extend(["--watermark-scale", str(request.watermark_scale)])
        command.extend(["--watermark-margin-x", str(request.watermark_margin_x)])
        command.extend(["--watermark-margin-y", str(request.watermark_margin_y)])
        if request.watermark_font_family:
            command.extend(["--watermark-font-family", request.watermark_font_family])
        if request.watermark_color:
            command.extend(["--watermark-color", request.watermark_color])

    command.append("--keep-intermediate")
    command.extend(["--output", str(OUTPUTS_DIR.resolve())])
    return command


def append_log(job_id: str, message: str) -> None:
    with jobs_lock:
        if job_id in jobs:
            job = jobs[job_id]
            job.logs = (job.logs + [message])[-120:]
            save_jobs_unlocked()


def run_job(job_id: str) -> None:
    try:
        with jobs_lock:
            request = jobs[job_id].request

        secret = job_secrets.get(job_id)
        if secret:
            request = request.model_copy(update={"ai_api_key": secret})

        started_at = time.time()
        set_job(job_id, status="running", error=None)
        command = build_clipper_command(request)
        append_log(job_id, f"Command: {' '.join(command)}")
        print(f"[job {job_id}] Command: {' '.join(command)}", flush=True)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        if getattr(sys, "frozen", False):
            env.setdefault("SULTANCLIP_DATA_DIR", str(resolve_data_dir()))
            env["PYTHONNOUSERSITE"] = "1"
            popen_cwd = resolve_data_dir()
        else:
            popen_cwd = BASE_DIR

        append_log(job_id, "Starting pipeline...")

        process = subprocess.Popen(
            command,
            cwd=popen_cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        append_log(job_id, f"Pipeline started (PID: {process.pid})")

        logs: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            cleaned = line.rstrip()
            if cleaned:
                logs.append(cleaned)
                set_job(job_id, logs=logs[-120:])

        code = process.wait()
        append_log(job_id, f"Pipeline exited (code: {code})")
        clips = discover_clips(started_at)
        candidates = discover_candidates(started_at)
        if code == 0:
            work_dir = discover_work_dir(started_at)
            updates = {"status": "completed", "logs": logs[-120:]}
            if work_dir:
                updates["work_dir"] = work_dir
            if clips:
                updates["clips"] = clips
            if candidates:
                updates["candidates"] = candidates
            set_job(job_id, **updates)
        else:
            set_job(
                job_id,
                status="failed",
                clips=clips,
                candidates=candidates,
                logs=logs[-120:],
                error=f"clipper.py exited with code {code}",
            )
        job_secrets.pop(job_id, None)

        # An uploaded source is only needed during processing; remove it afterwards
        # so large videos don't accumulate in uploads/.
        if request.source_file:
            upload_path = resolve_upload_path(request.source_file)
            if upload_path is not None:
                try:
                    upload_path.unlink()
                except OSError:
                    pass
    except Exception as exc:
        tb = traceback.format_exc()
        append_log(job_id, f"Pipeline crashed: {exc}")
        append_log(job_id, f"Traceback: {tb}")
        set_job(job_id, status="failed", error=f"Pipeline gagal: {exc}")
        job_secrets.pop(job_id, None)


@app.get("/api/model-status")
def model_status() -> dict[str, str | bool | float | None]:
    from model_cache import model_present, get_download_progress, get_current_model, resolve_data_dir

    name = get_current_model()
    return {
        "model_present": model_present(resolve_data_dir(), name),
        "model_name": name,
        "download_progress": get_download_progress(),
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class ModelsQuery(BaseModel):
    base_url: str = ""
    api_key: str = ""


@app.post("/api/models")
def list_models(query: ModelsQuery) -> dict[str, list[str]]:
    import urllib.request

    base = query.base_url.strip()
    if not base:
        raise HTTPException(status_code=400, detail="base_url is required")

    base = base.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
    url = base.rstrip("/") + "/models"
    request = urllib.request.Request(url, method="GET")
    request.add_header("Accept", "application/json")
    if query.api_key.strip():
        request.add_header("Authorization", f"Bearer {query.api_key.strip()}")

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to reach LLM endpoint: {exc}")

    data = payload.get("data") if isinstance(payload, dict) else None
    models = [
        item["id"]
        for item in (data or [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    models.sort()
    return {"models": models}


@app.post("/api/uploads")
def upload_video(file: UploadFile = File(...)) -> dict[str, str | float | None]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed}")

    stored_name = f"{uuid.uuid4().hex}{suffix}"
    target = UPLOADS_DIR / stored_name
    try:
        with target.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        file.file.close()

    return {
        "source_file": stored_name,
        "original_name": file.filename or stored_name,
        "duration": probe_media_duration(target),
    }


@app.post("/api/jobs/{job_id}/watermark-upload")
def upload_watermark(job_id: str, file: UploadFile = File(...)) -> dict[str, str]:
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not job.work_dir:
        raise HTTPException(status_code=404, detail="job has no work directory")

    filename = file.filename or ""
    is_png = (file.content_type == "image/png") or filename.lower().endswith(".png")
    if not is_png:
        raise HTTPException(status_code=422, detail="Only PNG images are accepted")

    work_dir = OUTPUTS_DIR / job.work_dir
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / "watermark.png"
    try:
        with target.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        file.file.close()

    return {"watermark_image": "watermark.png"}


@app.get("/api/probe")
def probe_url(url: str) -> dict[str, float | str | None]:
    from clipper import _ydl_base_opts

    ydl_opts = {**_ydl_base_opts(), "skip_download": True}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:  # noqa: BROAD_EXCEPT_OK — probe endpoint soft-fails
        return {"duration": None, "title": None}

    if not isinstance(info, dict):
        return {"duration": None, "title": None}
    duration = info.get("duration")
    title = info.get("title")
    return {
        "duration": float(duration) if duration else None,
        "title": str(title) if title else None,
    }


@app.post("/api/jobs", response_model=ClipJob)
def create_job(request: ClipJobRequest) -> ClipJob:
    if request.max_duration <= request.min_duration:
        raise HTTPException(status_code=400, detail="max_duration must be greater than min_duration")

    if not request.url and not request.source_file:
        raise HTTPException(status_code=400, detail="Provide a YouTube URL or upload a video first")

    if request.source_file:
        upload_path = resolve_upload_path(request.source_file)
        if upload_path is None:
            raise HTTPException(status_code=400, detail="Uploaded video not found; upload it again")
        request = request.model_copy(update={"source_file": str(upload_path)})

    request = normalize_job_request(request)
    if not request.name.strip():
        request = request.model_copy(
            update={"name": default_job_name(request.url, bool(request.source_file))}
        )
    job_id = uuid.uuid4().hex

    # Keep the API key out of persisted state and API responses.
    secret = request.ai_api_key
    if secret:
        job_secrets[job_id] = secret
    request = request.model_copy(update={"ai_api_key": ""})

    job = ClipJob(
        id=job_id,
        status="queued",
        request=request,
        created_at=now_iso(),
        updated_at=now_iso(),
        logs=["🔄 Menyiapkan pipeline..."],
    )
    with jobs_lock:
        jobs[job_id] = job
        save_jobs_unlocked()

    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()
    return job





@app.get("/api/jobs", response_model=list[ClipJob])
def list_jobs() -> list[ClipJob]:
    with jobs_lock:
        return sorted(jobs.values(), key=lambda job: job.created_at, reverse=True)


@app.delete("/api/jobs")
def delete_all_jobs() -> dict[str, str | int]:
    with jobs_lock:
        jobs.clear()
        job_secrets.clear()
        save_jobs_unlocked()
        removed_outputs = clear_outputs_dir()
        clear_uploads_dir()
    return {"status": "ok", "removed_outputs": removed_outputs}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict[str, str]:
    with jobs_lock:
        job = jobs.pop(job_id, None)
        job_secrets.pop(job_id, None)
        save_jobs_unlocked()
    if job and job.work_dir:
        work_path = OUTPUTS_DIR / job.work_dir
        if work_path.exists():
            shutil.rmtree(work_path, ignore_errors=True)
    return {"status": "ok"}


@app.get("/api/jobs/{job_id}", response_model=ClipJob)
def get_job(job_id: str) -> ClipJob:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _compute_peaks(wav_path: Path, num_points: int = 1000) -> list[int]:
    """Read a mono WAV via stdlib, return ~num_points RMS values in [-128, 127]."""
    with wave.open(str(wav_path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    # Only 16-bit PCM supported (clipper.py produces exactly this)
    if sampwidth != 2:
        return []

    fmt = f"<{n_frames * n_channels}h"
    samples = struct.unpack(fmt, raw)
    mono = samples[::n_channels]
    total = len(mono)
    if total == 0:
        return []

    stride = max(1, total // num_points)
    peaks: list[int] = []
    for i in range(0, total, stride):
        window = mono[i : i + stride]
        rms = math.sqrt(sum(s * s for s in window) / len(window))
        normalized = int((rms / 32768.0) * 255) - 128
        peaks.append(max(-128, min(127, normalized)))
        if len(peaks) >= num_points:
            break

    return peaks


def _get_peaks(work_dir: Path) -> list[int]:
    """Return cached peaks or compute+cache them. Never raises."""
    try:
        cache_path = work_dir / "peaks.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        wav_files = sorted(work_dir.glob("audio*.wav"), key=lambda p: p.stat().st_mtime)
        if not wav_files:
            return []

        peaks = _compute_peaks(wav_files[-1])
        cache_path.write_text(json.dumps(peaks), encoding="utf-8")
        return peaks
    except Exception:
        return []


@app.get("/api/jobs/{job_id}/timeline", response_model=TimelineData)
def get_job_timeline(job_id: str) -> TimelineData:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.work_dir:
        raise HTTPException(status_code=404, detail="Source not available")

    work_dir = OUTPUTS_DIR / job.work_dir
    source_path = next(work_dir.glob("source.*"), None)
    if not source_path:
        raise HTTPException(status_code=404, detail="Source not available")

    duration = probe_media_duration(source_path) or 0.0

    transcript_files = sorted(work_dir.glob("transcript*.json"), key=lambda p: p.stat().st_mtime)
    segments: list[TranscriptSegmentOut] = []
    if transcript_files:
        rows = json.loads(transcript_files[-1].read_text(encoding="utf-8"))
        segments = [TranscriptSegmentOut(**s) for s in rows]

    return TimelineData(
        source_url=clip_url(source_path),
        duration=duration,
        segments=segments,
        candidates=job.candidates,
        peaks=_get_peaks(work_dir),
    )


@app.post("/api/jobs/{job_id}/recut")
def recut_job(job_id: str, body: RecutRequest) -> dict[str, ClipFile | ClipCandidate]:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.work_dir:
        raise HTTPException(status_code=404, detail="Source not available")

    try:
        new_clip, new_cand = recut_clip(job, body.index, body.start, body.end, body.segments, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    new_clips = [new_clip if c.name == new_clip.name else c for c in job.clips]
    new_cands = [new_cand if c.index == body.index else c for c in job.candidates]
    set_job(job_id, clips=new_clips, candidates=new_cands)

    return {"clip": new_clip.model_dump(), "candidate": new_cand.model_dump()}
