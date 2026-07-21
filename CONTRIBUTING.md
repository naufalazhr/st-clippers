# Contributing

Thanks for improving ClipForge.

## Local setup

Backend:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8010
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:3000`.

## Desktop installer build

Prerequisites: Rust toolchain, Python 3.12, Node.js 22.

```bash
cd frontend && npm ci && npm run build && cd ..
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt pyinstaller && bash build_bundle.sh && cd ..
mkdir -p desktop/src-tauri/binaries
cp backend/dist/sultanclip-backend/sultanclip-backend desktop/src-tauri/binaries/sultanclip-backend-aarch64-apple-darwin
cd desktop && npm ci && npx tauri build --target aarch64-apple-darwin
```

On Windows: the sidecar suffix is `x86_64-pc-windows-msvc.exe` and `--target` is omitted.

## Checks

Run these before sending a change:

```powershell
py -m py_compile backend\api.py backend\clipper.py
cd frontend
npm run build
```

## Pull requests

- Keep changes focused.
- Include screenshots or short notes for UI changes.
- Mention tested commands.
- Do not commit generated clips, local outputs, `.env` files, or `jobs.json`.

## Good first issues

- Better clip scoring.
- Queue controls and job cancellation.
- Auth/rate limiting for server deployments.
- Export presets for TikTok, Reels, and Shorts.
- Better transcript cleanup for more languages.
