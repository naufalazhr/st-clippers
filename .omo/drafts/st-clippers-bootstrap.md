# st-clippers-bootstrap - Draft

## Intent
- intent: clear
- review_required: false
- Classify: Standard (clone + run + rebrand + push; ~6 files touched: README, LICENSE, backend/README, docker-compose, package.json, .env)

## Status
- status: approved (user answered F1-F4 on 2026-07-20)
- pending action: write .omo/plans/st-clippers-bootstrap.md + append todos + fill TL;DR

## Decisions (user-answered forks)
- F1 run path: Docker Compose (user accepted default)
- F2 repo name: `st-clippers`; visibility: private (adopted default — user didn't specify, reversible)
- F3 git strategy: new empty repo + `upstream` remote manual (user accepted default)
- F4 attribution: (c) rebrand total, preserve MIT notice (user chose c)

## Adopted defaults (not asked, reversible)
- Branch rename `master`→`main` before push (2026 convention)
- `gh` CLI for repo creation; fallback HTTPS+PAT or SSH if not authed
- ffmpeg NOT needed on host for Docker path (container installs deps via apt)
- "improve dan modifikasi app/system" is OUT of scope — separate future plan
- `backend/uploads/` dir created by compose volume mount; add to .gitignore if missing

## Components ledger
| ID | Outcome | Status | Evidence path |
|----|---------|--------|---------------|
| C1 | Upstream repo cloned into project folder | pending | `.git/` + `backend/` + `frontend/` + `docker-compose.yml` present |
| C2 | Backend runs locally via Docker | pending | `curl http://localhost:8010/api/health` → 200 JSON |
| C3 | Frontend runs locally via Docker | pending | `curl -I http://localhost:3000` → 200 |
| C4 | New private GitHub repo `naufalazhr/st-clippers` created + pushed | pending | `git push -u origin main` succeeds; fresh clone verifies |

## Planned waves
- Wave 1 (2 todos): verify local tooling + clone upstream into non-empty folder
- Wave 2 (3 todos): env config + docker compose up + smoke test
- Wave 3 (2 todos): rebrand to ST Clippers + create new repo & remotes & push
- Wave 4 (1 todo): verify push via fresh clone
- Final wave (4 parallel): F1 compliance, F2 quality, F3 manual QA, F4 scope fidelity

## Key facts (from upstream exploration)
- Repo: github.com/mallexibra-dev/clipforge, default branch `master`, MIT license
- Backend: Python 3.12-slim Dockerfile, FastAPI, faster-whisper==1.2.1, yt-dlp==2026.6.9, opencv-python>=4.10.0, uvicorn==0.38.0, imageio-ffmpeg, pydantic, python-slugify, rich
- `backend/llm.py`: optional OpenAI-compatible LLM integration, `AIConfig.enabled=False` by default — no API key needed for local run
- `backend/models/face_detection_yunet_2023mar.onnx`: 232KB face detection model for smart crop
- Frontend: Next.js ^16.1.0, React ^19.2.3, lucide-react, react-hot-toast; both `bun.lock` and `package-lock.json` present
- Docker Compose: 2 services, backend port 8010, frontend port 3000, volumes for outputs/uploads/jobs.json
- `.env.docker.example`: FRONTEND_PORT, BACKEND_PORT, NEXT_PUBLIC_API_BASE
- frontend/.env.example: NEXT_PUBLIC_API_BASE + BACKEND_API_BASE (both http://127.0.0.1:8010)
- backend/README.md is Windows-flavored (powershell, `.venv\Scripts\`) — needs macOS/Unix conversion
- `backend/tests/` directory exists but empty; `pytest.ini` present
- `backend/uploads/` referenced in compose but not in root .gitignore — add it
- Root .gitignore already covers: .env, backend/.venv, backend/outputs, backend/jobs.json, frontend/.next, frontend/node_modules

## Risks
- First Docker build pulls faster-whisper model (~500MB for Systran/faster-whisper-small) — slow on first run
- opencv-python in Docker needs libgl1/libglib2.0 (already in Dockerfile apt-get)
- macOS Docker Desktop must have ≥4GB RAM allocated or opencv build may OOM
- `gh` may not be authenticated → plan includes fallback path
- Folder not empty (`.codegraph/`, `.omo/` exist) → can't bare `git clone .`; use `git init` + remote + fetch + checkout
