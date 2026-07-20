# st-clippers-bootstrap - Work Plan

## TL;DR (For humans)

**What you'll get.** Upstream `mallexibra-dev/clipforge` cloned into `/Users/naufal/Documents/Sultan Tech/ST Clippers` (preserving pre-existing `.codegraph/` and `.omo/`), running locally via `docker compose` (backend `:8010`, frontend `:3000`), rebranded to "ST Clippers" (5 files edited, MIT + NOTICE preserved), pushed to a new **private** repo `naufalazhr/st-clippers` on branch `main`, with `upstream` remote pointing back to clipforge for future pulls.

**Why this approach.** Docker Compose is the lowest-friction run path (matches upstream README, no native ffmpeg/python/node installs). New empty repo + manual `upstream` remote (not a GitHub fork) gives full flexibility for the modification phase without fork-metadata constraints. Rebrand is scoped tightly to 5 files to stay MIT-compliant and avoid scope-creep into the app-improvement phase (explicitly OUT of scope).

**What it will NOT do.**
- No app/system improvements or modifications (separate future plan).
- No rebase or history rewrite of upstream commits — full upstream history preserved as-is.
- No `.gitignore` edits (upstream `.gitignore` is sufficient; `backend/uploads/` is auto-created at runtime and gitignored via `backend/.gitignore` — verified).
- No CI, no deployment config, no secrets management.
- No changes to `backend/clipper.py`, `backend/api.py`, `backend/llm.py`, `backend/models/`, frontend `app/`, `lib/`, `types/`, `public/`, Dockerfiles, `next.config.ts`, `tsconfig.json`, `requirements.txt`, `pytest.ini`, or any test files.
- No deletion or force-push to the `upstream` remote (read-only).

**Effort.** ~4 todos + 4 parallel final checks. First Docker build pulls faster-whisper model (~500MB) — allow 10-30 min; subsequent builds cached.

**Risk.** Low. Main risks: Docker Desktop RAM <4GB (opencv OOM), `gh` not authenticated (fallback to PAT/SSH), path-with-space in working dir (quote all paths).

**Decisions.**
- F1 run path: Docker Compose (user-approved)
- F2 repo: `st-clippers`, private (user-specified name; visibility adopted default)
- F3 git: new empty repo + manual `upstream` remote (user-approved)
- F4 attribution: rebrand total, preserve MIT copyright + add second line + preserve NOTICE unchanged (user chose option c)

## Scope

**In scope:**
1. Clone `https://github.com/mallexibra-dev/clipforge` (branch `master`) into `/Users/naufal/Documents/Sultan Tech/ST Clippers` without destroying `.codegraph/` or `.omo/`.
2. Create `.env` from `.env.docker.example` with default ports (backend 8010, frontend 3000, `NEXT_PUBLIC_API_BASE=http://localhost:8010`).
3. Run `docker compose --env-file .env up -d --build` and verify both services healthy.
4. Rebrand exactly 5 files:
   - `README.md` (root): title → "ST Clippers", convert powershell → bash for macOS, update author/link.
   - `backend/README.md`: title → "ST Clippers Backend", convert powershell → bash, update output description.
   - `docker-compose.yml`: `container_name` values → `st-clippers-backend` / `st-clippers-frontend`.
   - `frontend/package.json`: `"name"` field → `"st-clippers"`.
   - `LICENSE`: preserve existing `Copyright (c) 2026 mallexibra` line, add `Copyright (c) 2026 Naufal Azhar` below it, preserve rest of MIT text unchanged.
5. Preserve `NOTICE` file unchanged (verified present, contains YuNet attribution).
6. Rename local branch `master` → `main`.
7. Create private GitHub repo `naufalazhr/st-clippers` via `gh` CLI (fallback: HTTPS+PAT or SSH if `gh` not authed).
8. Set `origin` → new repo, `upstream` → `https://github.com/mallexibra-dev/clipforge.git`.
9. Push `main` to `origin` (includes full upstream history + rebrand commit).
10. Verify push via fresh clone to temp dir.

**Out of scope:**
- Any app/system improvements or modifications (separate future plan).
- Rebase, squash, or history rewrite of upstream commits.
- `.gitignore` edits, new config files, CI, deployment, secrets.
- Running the app post-rebrand for functional QA beyond endpoint smoke tests.
- Changes to any file not in the 5-file rebrand list above.

## Verification strategy

All verification is agent-executed (zero user intervention). Each step has a concrete command + expected output:

| Check | Command | Expected |
|-------|---------|----------|
| Clone success | `git -C "<dir>" rev-parse HEAD` | Matches `git ls-remote https://github.com/mallexibra-dev/clipforge master` |
| `.omo/` survived | `test -d "<dir>/.omo"` | exit 0 |
| `.codegraph/` survived | `test -d "<dir>/.codegraph"` | exit 0 |
| Backend health | `curl -fsS http://localhost:8010/api/health` | `{"status":"ok"}` |
| Backend container | `docker compose ps backend` | status `Up` |
| Frontend reachable | `curl -fsSI http://localhost:3000` | HTTP/2 200 |
| Frontend container | `docker compose ps frontend` | status `Up` |
| Rebrand: README | `grep -qi "ST Clippers" README.md` | exit 0 |
| Rebrand: no ClipForge in title | `head -5 README.md \| grep -vi clipforge` | exit 0 |
| Rebrand: backend README bash | `grep -q "source .venv/bin/activate" backend/README.md` | exit 0 |
| Rebrand: container names | `grep -q st-clippers-backend docker-compose.yml` | exit 0 |
| Rebrand: package.json | `jq -e '.name == "st-clippers"' frontend/package.json` | exit 0 |
| Rebrand: LICENSE | `grep -q "Copyright (c) 2026 Naufal Azhar" LICENSE` | exit 0 |
| NOTICE preserved | `git diff NOTICE` | empty |
| Branch is main | `git branch --show-current` | `main` |
| origin remote | `git remote get-url origin` | `https://github.com/naufalazhr/st-clippers.git` (or SSH) |
| upstream remote | `git remote get-url upstream` | `https://github.com/mallexibra-dev/clipforge.git` |
| Push success | `git log origin/main..main --oneline` | empty |
| Fresh clone | `git clone https://github.com/naufalazhr/st-clippers.git /tmp/verify-$(date +%s)` | exit 0 |
| Fresh clone: branch | `git -C /tmp/verify-* branch --show-current` | `main` |
| Fresh clone: HEAD matches | `git -C /tmp/verify-* rev-parse HEAD` | equals local HEAD |
| No stray edits | `git diff upstream/master..main --stat` | only 5 rebrand files in diff |

## Execution strategy

**Wave ordering (sequential):**
1. **Wave 1 — Verify tooling + clone.** Check docker, docker compose, git, gh (or fallback). Clone upstream into non-empty folder using safe strategy (`git init` + `git fetch` + `git checkout` — safe because upstream has no `.omo/` or `.codegraph/` paths, verified via `git ls-tree`). Verify `.omo/` and `.codegraph/` survived.
2. **Wave 2 — Run locally.** Create `.env` from `.env.docker.example`. `docker compose up -d --build`. Smoke-test both endpoints. Note: first build slow (model pull).
3. **Wave 3 — Rebrand + git housekeeping.** Edit 5 files (atomic). Verify NOTICE untouched. Rename `master`→`main`. Set remotes (`origin`, `upstream`). Commit.
4. **Wave 4 — Create repo + push + fresh-clone verify.** `gh repo create` (or fallback). Push. Fresh clone to temp. Verify integrity.

**Rollback per wave:**
- Wave 1 fail: nothing to roll back (folder state unchanged if clone aborted; `.omo/`/`.codegraph/` intact).
- Wave 2 fail: `docker compose down -v` to remove containers + volumes. `.env` can be deleted.
- Wave 3 fail: `git checkout -- .` to discard uncommitted rebrand edits; `git branch -m main master` to undo rename; `git remote remove origin` / `git remote remove upstream`.
- Wave 4 fail (repo created but push failed): `gh repo delete naufalazhr/st-clippers --yes` (if gh) or delete via web; local state intact for retry.

**Parallelization:** Final verification wave runs 4 checks in parallel. All other waves strictly sequential (each depends on prior).

## Todos

- [x] 1. Verify local tooling and clone upstream into non-empty folder
**References:**
- Working dir: `/Users/naufal/Documents/Sultan Tech/ST Clippers` (note: space in path, quote everywhere)
- Upstream: `https://github.com/mallexibra-dev/clipforge`, branch `master`
- Pre-existing dirs to preserve: `.codegraph/`, `.omo/`
- Verified: upstream `master` tree has NO `.omo/` or `.codegraph/` paths (checked via GitHub contents API — root listing shows only: `.dockerignore`, `.env.docker.example`, `.gitignore`, `CONTRIBUTING.md`, `LICENSE`, `NOTICE`, `README.md`, `SECURITY.md`, `backend/`, `docker-compose.yml`, `frontend/`, `image.png`)

**Steps:**
1. Verify tooling (all must succeed):
   ```bash
   docker --version
   docker compose version
   git --version
   gh --version && gh auth status
   ```
   If `gh` missing or not authed, record fallback: user must provide a GitHub PAT (classic or fine-grained with `repo` scope) or SSH key. Do NOT proceed to Wave 4 without auth resolved; Wave 1-3 can still complete.
2. Verify pre-existing dirs:
   ```bash
   test -d "/Users/naufal/Documents/Sultan Tech/ST Clippers/.omo" && echo "omo OK"
   test -d "/Users/naufal/Documents/Sultan Tech/ST Clippers/.codegraph" && echo "codegraph OK"
   ```
3. Clone into non-empty folder (safe strategy — git only touches tracked files, pre-existing untracked dirs survive):
   ```bash
   cd "/Users/naufal/Documents/Sultan Tech/ST Clippers"
   git init
   git remote add origin https://github.com/mallexibra-dev/clipforge.git
   git fetch origin master
   git checkout -b master FETCH_HEAD
   ```
   If `git checkout` refuses due to untracked file collision (shouldn't happen per verification, but guard): abort and report — do NOT use `-f`.
4. Verify upstream HEAD:
   ```bash
   cd "/Users/naufal/Documents/Sultan Tech/ST Clippers"
   git rev-parse HEAD
   git ls-remote https://github.com/mallexibra-dev/clipforge master
   ```
   Local HEAD must match remote HEAD SHA.

**Acceptance criteria (agent-executable):**
- `git -C "<dir>" rev-parse HEAD` returns a SHA matching `git ls-remote https://github.com/mallexibra-dev/clipforge master` output (first column).
- `test -d "<dir>/.omo"` exit 0.
- `test -d "<dir>/.codegraph"` exit 0.
- `test -f "<dir>/backend/api.py"` exit 0.
- `test -f "<dir>/docker-compose.yml"` exit 0.
- `git -C "<dir>" remote get-url origin` returns `https://github.com/mallexibra-dev/clipforge.git`.
- `git -C "<dir>" status --porcelain` shows clean working tree (no merge conflicts, no deleted `.omo/`/`.codegraph/`).

**QA scenarios:**
- Happy: all 4 tooling commands exit 0; clone succeeds; `.omo/` and `.codegraph/` present post-clone.
- Failure A — Docker not running: `docker --version` succeeds but `docker compose up` later fails. Record error, instruct user to start Docker Desktop. Do not mark T1 failed (tooling present, runtime issue caught in T2).
- Failure B — `git checkout` refuses (untracked file collision): this means upstream added a `.omo/` or `.codegraph/` path since verification. Abort. Report exact conflicting path. Do NOT force.
- Evidence path: `<dir>/.omo/verification/t1-clone.log` (capture all command outputs).

**Commit:** None (clone brings upstream history; no new commit yet).

---

- [x] 2. Configure env and run backend + frontend via Docker Compose
**References:**
- `.env.docker.example` (upstream, verified contents):
  ```
  FRONTEND_PORT=3000
  BACKEND_PORT=8010
  NEXT_PUBLIC_API_BASE=http://localhost:8010
  ```
- `docker-compose.yml` (upstream): 2 services, backend port 8010, frontend port 3000, volumes for `outputs/`, `uploads/`, `jobs.json`.
- Backend health endpoint (verified in `backend/api.py`): `GET /api/health` → `{"status":"ok"}`.
- Frontend Dockerfile (verified): `npm ci` + `npm run build` + `npm run start` (production server, not dev).
- First build downloads `Systran/faster-whisper-small` model (~500MB) — allow 10-30 min.

**Steps:**
1. Create `.env`:
   ```bash
   cd "/Users/naufal/Documents/Sultan Tech/ST Clippers"
   cp .env.docker.example .env
   ```
2. Verify `.env` contents:
   ```bash
   grep -q "^BACKEND_PORT=8010$" .env
   grep -q "^FRONTEND_PORT=3000$" .env
   grep -q "^NEXT_PUBLIC_API_BASE=http://localhost:8010$" .env
   ```
3. Build and start (long first build — do not timeout under 30 min):
   ```bash
   cd "/Users/naufal/Documents/Sultan Tech/ST Clippers"
   docker compose --env-file .env up -d --build 2>&1 | tee .omo/verification/t2-build.log
   ```
   If build OOMs (exit code 137): instruct user to increase Docker Desktop RAM to ≥4GB (Settings → Resources → Memory), then retry. Record in log.
4. Wait for both services healthy (poll up to 120s after build completes):
   ```bash
   for i in $(seq 1 12); do
     sleep 10
     if curl -fsS http://localhost:8010/api/health >/dev/null 2>&1; then echo "backend ready"; break; fi
   done
   ```
5. Smoke test:
   ```bash
   curl -fsS http://localhost:8010/api/health
   curl -fsSI http://localhost:3000
   docker compose ps
   docker compose logs --tail=50 backend
   docker compose logs --tail=50 frontend
   ```

**Acceptance criteria (agent-executable):**
- `curl -fsS http://localhost:8010/api/health` returns exactly `{"status":"ok"}`.
- `curl -fsSI http://localhost:3000 2>/dev/null | head -1` returns line containing `200`.
- `docker compose ps backend` output contains `Up` (not `Exited`, not `Restarting`).
- `docker compose ps frontend` output contains `Up`.
- `docker compose logs --tail=50 backend 2>&1 | grep -iE "error|traceback"` returns no matches (warnings OK).
- `docker compose logs --tail=50 frontend 2>&1 | grep -iE "error|failed"` returns no matches (warnings OK).

**QA scenarios:**
- Happy: build completes, both services `Up`, health endpoint returns `{"status":"ok"}`, frontend returns 200.
- Failure A — build OOM (exit 137): record log, instruct user to raise Docker Desktop RAM to ≥4GB, retry. Do not mark T2 complete until both services `Up`.
- Failure B — backend health 404/connection refused after 120s: `docker compose logs backend` for traceback. Common cause: `jobs.json` volume mount points to nonexistent host file (compose creates it as dir). Fix: `touch backend/jobs.json` before `up`. Record fix in log.
- Failure C — frontend build fails (`npm ci` error): check `package-lock.json` integrity. Record log, do not retry blindly.
- Evidence path: `<dir>/.omo/verification/t2-build.log`, `t2-smoke.log`.

**Commit:** None (`.env` is gitignored).

---

- [x] 3. Rebrand to ST Clippers (5 files) + git housekeeping
**References:**
- `README.md` (upstream root): title `# ClipForge`, Windows-flavored local dev instructions (powershell `.venv\Scripts\`).
- `backend/README.md` (upstream): title `# ClipForge Backend`, powershell commands, output structure docs.
- `docker-compose.yml` (upstream): `container_name: clipforge-backend`, `container_name: clipforge-frontend`.
- `frontend/package.json` (upstream): `"name": "clipforge-frontend"`.
- `LICENSE` (upstream, verified): `Copyright (c) 2026 mallexibra` + standard MIT text.
- `NOTICE` (upstream, verified): YuNet face detector attribution + dependency notes. MUST NOT CHANGE.
- Root `.gitignore` (upstream, verified): covers `.env`, `backend/.venv/`, `backend/outputs/`, `backend/jobs.json`, `frontend/.next/`, `frontend/node_modules/`.

**Must NOT touch (scope guardrail):**
- `NOTICE` — preserve unchanged.
- `backend/clipper.py`, `backend/api.py`, `backend/llm.py`, `backend/requirements.txt`, `backend/pytest.ini`, `backend/Dockerfile`, `backend/.dockerignore`, `backend/.gitignore`, `backend/models/`, `backend/tests/`.
- `frontend/app/`, `frontend/lib/`, `frontend/types/`, `frontend/public/`, `frontend/Dockerfile`, `frontend/next.config.ts`, `frontend/tsconfig.json`, `frontend/.dockerignore`, `frontend/.gitignore`, `frontend/.env.example`, `frontend/bun.lock`, `frontend/package-lock.json`.
- `.dockerignore`, `.env.docker.example`, `.gitignore`, `CONTRIBUTING.md`, `SECURITY.md`, `image.png`.

**Steps:**
1. Edit `README.md`:
   - Change `# ClipForge` → `# ST Clippers` (h1 title only).
   - Convert local dev section powershell → bash:
     - `py -m venv .venv` → `python3 -m venv .venv`
     - `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` → `source .venv/bin/activate && pip install -r requirements.txt`
     - `.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8010` → `source .venv/bin/activate && uvicorn api:app --host 127.0.0.1 --port 8010`
     - `cd frontend` / `npm install` / `npm run dev` stay (already cross-platform).
   - Convert CLI usage section powershell → bash (same `.venv\Scripts\python.exe` → `python` after activate pattern).
   - Update "Author" section: change `Created by [mallexibra](https://mallexibra.my.id/).` → `Forked from [ClipForge](https://github.com/mallexibra-dev/clipforge) by [mallexibra](https://mallexibra.my.id/). Modified by Naufal Azhar.`
   - Preserve all other sections (Overview, Features, Requirements, Quick Start With Docker, API, Configuration, Safety, Project Structure, License).
2. Edit `backend/README.md`:
   - Change `# ClipForge Backend` → `# ST Clippers Backend`.
   - Convert all powershell code blocks to bash:
     - `py -m venv .venv` → `python3 -m venv .venv`
     - `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` → `source .venv/bin/activate && pip install -r requirements.txt`
     - `.\.venv\Scripts\python.exe clipper.py "..."` → `python clipper.py "..."`
     - `.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8010` → `uvicorn api:app --host 127.0.0.1 --port 8010`
   - Preserve output structure, default video specs, notes sections.
3. Edit `docker-compose.yml`:
   - `container_name: clipforge-backend` → `container_name: st-clippers-backend`
   - `container_name: clipforge-frontend` → `container_name: st-clippers-frontend`
   - Change nothing else.
4. Edit `frontend/package.json`:
   - `"name": "clipforge-frontend"` → `"name": "st-clippers"`
   - Change nothing else.
5. Edit `LICENSE`:
   - After the line `Copyright (c) 2026 mallexibra`, add a new line: `Copyright (c) 2026 Naufal Azhar`
   - Preserve all other text unchanged.
6. Verify NOTICE unchanged:
   ```bash
   cd "/Users/naufal/Documents/Sultan Tech/ST Clippers"
   git diff NOTICE
   ```
   Must be empty.
7. Verify no stray edits:
   ```bash
   git diff --stat
   ```
   Must show exactly: `README.md`, `backend/README.md`, `docker-compose.yml`, `frontend/package.json`, `LICENSE`. No other files.
8. Rename branch `master` → `main`:
   ```bash
   git branch -m master main
   ```
9. Add `upstream` remote (keep `origin` as clipforge for now; T4 will reassign `origin`):
   ```bash
   git remote add upstream https://github.com/mallexibra-dev/clipforge.git
   git remote -v
   ```
   (origin → clipforge, upstream → clipforge. T4 reassigns origin.)
10. Commit:
    ```bash
    git add README.md backend/README.md docker-compose.yml frontend/package.json LICENSE
    git commit -m "chore: rebrand to ST Clippers

- Rename project title in root + backend READMEs
- Convert PowerShell commands to bash (macOS/Unix)
- Update docker-compose container_name to st-clippers-*
- Rename frontend package to st-clippers
- Add second copyright line (Naufal Azhar) to LICENSE
- Preserve MIT license text and NOTICE file unchanged
- No functional code changes

Forked from mallexibra-dev/clipforge (MIT)."
    ```

**Acceptance criteria (agent-executable):**
- `grep -qi "^# ST Clippers$" README.md` exit 0.
- `head -1 README.md | grep -qi clipforge` exit 1 (no ClipForge in h1).
- `grep -q "source .venv/bin/activate" README.md` exit 0.
- `! grep -q '\\.venv\\\\Scripts' README.md` exit 0 (no powershell venv paths).
- `grep -qi "^# ST Clippers Backend$" backend/README.md` exit 0.
- `! grep -q '\\.venv\\\\Scripts' backend/README.md` exit 0.
- `grep -q "st-clippers-backend" docker-compose.yml` exit 0.
- `grep -q "st-clippers-frontend" docker-compose.yml` exit 0.
- `! grep -E "container_name:.*clipforge" docker-compose.yml` exit 0.
- `jq -e '.name == "st-clippers"' frontend/package.json` exit 0.
- `grep -q "^Copyright (c) 2026 mallexibra$" LICENSE` exit 0 (original preserved).
- `grep -q "^Copyright (c) 2026 Naufal Azhar$" LICENSE` exit 0 (new line added).
- `git diff NOTICE` output is empty.
- `git diff --stat HEAD~1` shows exactly 5 files: `README.md`, `backend/README.md`, `docker-compose.yml`, `frontend/package.json`, `LICENSE`.
- `git branch --show-current` returns `main`.
- `git remote get-url upstream` returns `https://github.com/mallexibra-dev/clipforge.git`.

**QA scenarios:**
- Happy: all 5 files edited, NOTICE untouched, branch renamed, commit created, no stray files in diff.
- Failure A — `git diff NOTICE` shows changes: accidental edit. `git checkout NOTICE` to revert, re-commit.
- Failure B — `git diff --stat` shows >5 files: stray edit. `git checkout -- <stray-file>` for each, re-commit.
- Failure C — `git branch -m` fails (branch already named `main` or not on `master`): `git branch --show-current` to check current name; if already `main`, skip rename.
- Evidence path: `<dir>/.omo/verification/t3-rebrand.log` (capture `git diff --stat`, `git diff NOTICE`, `git log --oneline -1`, `git remote -v`).

**Commit:** `chore: rebrand to ST Clippers` (single atomic commit, message above).

---

- [x] 4. Create GitHub repo, reassign origin, push, and verify via fresh clone
**References:**
- New repo: `naufalazhr/st-clippers`, **private**.
- Current remotes (after T3): `origin` → clipforge, `upstream` → clipforge.
- Target remotes (after T4): `origin` → `naufalazhr/st-clippers`, `upstream` → clipforge (unchanged).
- Branch: `main` (renamed in T3).
- `gh` CLI: may or may not be authed (checked in T1).

**Steps:**
1. Create new private repo (path A: `gh` authed):
   ```bash
   gh repo create naufalazhr/st-clippers --private --description "ST Clippers - YouTube to vertical clips tool (forked from clipforge)"
   ```
   Path B (`gh` not authed, user provides PAT):
   ```bash
   # User provides PAT with repo scope. Store temporarily (not committed).
   GH_PAT="<user-provided>"
   curl -fsS -X POST -H "Authorization: token ${GH_PAT}" \
     -H "Accept: application/vnd.github+json" \
     https://api.github.com/user/repos \
     -d '{"name":"st-clippers","private":true,"description":"ST Clippers - YouTube to vertical clips tool (forked from clipforge)"}'
   ```
   Path C (SSH): user creates repo manually via github.com web UI, then proceed to step 2.
2. Reassign `origin` to new repo:
   ```bash
   cd "/Users/naufal/Documents/Sultan Tech/ST Clippers"
   git remote set-url origin https://github.com/naufalazhr/st-clippers.git
   # Or if using SSH: git remote set-url origin git@github.com:naufalazhr/st-clippers.git
   git remote -v
   ```
   Verify: `origin` → `naufalazhr/st-clippers`, `upstream` → `mallexibra-dev/clipforge`.
3. Push `main` with full history:
   ```bash
   git push -u origin main
   ```
   This pushes upstream's full commit history + the rebrand commit.
4. Fresh clone verification:
   ```bash
   VERIFY_DIR="/tmp/verify-st-clippers-$(date +%s)"
   git clone https://github.com/naufalazhr/st-clippers.git "$VERIFY_DIR"
   cd "$VERIFY_DIR"
   git rev-parse HEAD
   git branch --show-current
   git remote -v
   ```
5. Compare HEADs:
   ```bash
   LOCAL_HEAD=$(git -C "/Users/naufal/Documents/Sultan Tech/ST Clippers" rev-parse HEAD)
   CLONE_HEAD=$(git -C "$VERIFY_DIR" rev-parse HEAD)
   test "$LOCAL_HEAD" = "$CLONE_HEAD" && echo "HEADS MATCH"
   ```
6. Verify fresh clone has no `upstream` remote leaked:
   ```bash
   git -C "$VERIFY_DIR" remote -v | grep upstream
   ```
   Must return empty (upstream remote is local-only, not pushed).
7. Cleanup temp clone:
   ```bash
   rm -rf "$VERIFY_DIR"
   ```

**Acceptance criteria (agent-executable):**
- `git remote get-url origin` returns URL containing `naufalazhr/st-clippers`.
- `git remote get-url upstream` returns `https://github.com/mallexibra-dev/clipforge.git`.
- `git log origin/main..main --oneline` output is empty (nothing unpushed).
- Fresh clone command exits 0.
- `git -C "$VERIFY_DIR" rev-parse HEAD` equals `git -C "<dir>" rev-parse HEAD`.
- `git -C "$VERIFY_DIR" branch --show-current` returns `main`.
- `git -C "$VERIFY_DIR" remote -v` shows only `origin` (no `upstream`).
- `test -f "$VERIFY_DIR/LICENSE"` exit 0.
- `test -f "$VERIFY_DIR/NOTICE"` exit 0.
- `test -f "$VERIFY_DIR/docker-compose.yml"` exit 0.

**QA scenarios:**
- Happy: repo created, origin reassigned, push succeeds, fresh clone matches HEAD, no upstream leak, temp cleaned.
- Failure A — `gh repo create` fails (auth): record `gh auth status` output. Switch to Path B (PAT) or Path C (manual). Do not proceed until repo exists.
- Failure B — `git push` fails (non-fast-forward): should not happen (new empty repo). If it does, repo wasn't empty — `gh repo delete` and recreate. Record error.
- Failure C — fresh clone HEAD mismatch: push was partial. `git push -u origin main --force` (safe — new repo, no other contributors). Record.
- Failure D — fresh clone has `upstream` remote: impossible (remotes aren't pushed), but if observed, indicates upstream was accidentally set as origin. Fix remotes, re-push.
- Evidence path: `<dir>/.omo/verification/t4-push.log`, `t4-fresh-clone.log`.

**Commit:** None (push only; commit was in T3).

---

## Final verification wave

Run all 4 in parallel. ALL must APPROVE. Surface results and wait for user's explicit okay before declaring complete.

- [x] F1. Plan compliance audit
**Check:** every todo T1-T4 acceptance criterion passes. Re-run all acceptance commands. Any fail → reject.
**Evidence:** `<dir>/.omo/verification/f1-compliance.log`

- [x] F2. Code quality review (rebrand diff only)
**Check:** `git diff upstream/master..main --stat` shows exactly 5 files. `git diff upstream/master..main` reviewed — no accidental code logic changes, only text/config renames. No secrets, no API keys, no `.env` content in diff.
**Evidence:** `<dir>/.omo/verification/f2-quality.log`

- [x] F3. Automated runtime QA (re-run smoke tests)
**Check:** `curl -fsS http://localhost:8010/api/health` returns `{"status":"ok"}`. `curl -fsSI http://localhost:3000` returns 200. `docker compose ps` shows both `Up`. (Confirms rebrand didn't break runtime — container_name changes require `docker compose down && docker compose up -d` to pick up new names. If containers still running under old names, restart.)
**Evidence:** `<dir>/.omo/verification/f3-runtime.log`

- [x] F4. Scope fidelity audit
**Check:** `git diff upstream/master..main --stat` file list is exactly `{README.md, backend/README.md, docker-compose.yml, frontend/package.json, LICENSE}`. NOTICE does NOT appear in diff. No `.gitignore` changes. No new files added. No deletions.
**Evidence:** `<dir>/.omo/verification/f4-scope.log`

## Commit strategy

**Single commit on top of upstream history:**
- Message: `chore: rebrand to ST Clippers` (full message in T3).
- Contains exactly 5 file changes.
- Pushed to `origin/main` (new repo) with full upstream history.

**No other commits.** The clone (T1) brings upstream history unchanged. The env config (T2) is gitignored. The repo creation + push (T4) adds no commits.

**No rebase, no squash, no force-push** (unless F3 failure C triggers safe force-push to empty new repo).

## Success criteria

Plan is complete when ALL of the following are true:
1. T1-T4 acceptance criteria all pass (F1 approves).
2. `git diff upstream/master..main --stat` shows exactly 5 rebrand files (F2 + F4 approve).
3. Backend `:8010/api/health` returns `{"status":"ok"}` and frontend `:3000` returns 200 (F3 approves).
4. `git remote -v` shows `origin` → `naufalazhr/st-clippers` and `upstream` → `mallexibra-dev/clipforge`.
5. `git branch --show-current` returns `main`.
6. `git log origin/main..main --oneline` is empty (fully pushed).
7. Fresh clone to temp dir verifies HEAD match + no upstream remote leak.
8. Working tree clean (`git status --porcelain` empty, ignoring `.omo/` and `.codegraph/` which are untracked).
