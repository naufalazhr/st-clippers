# sultan-clip-rebrand - Work Plan

## TL;DR (For humans)

**What you'll get.** Sultan Clip — rebranded dark-mode-first clip generation tool. Gold regal accent throughout. Text-only "Sultan Clip" wordmark with gold gradient. Theme toggle (dark default + light). All Mallexibra/saweria/buy-me-coffee identity stripped. New gold "SC" favicon. Backend API title + docs updated to match.

**Why this approach.** Dark-mode-first with toggle gives modern clean aesthetic the user asked for while preserving accessibility. Gold (#D4A017 dark / #B8860B light) evokes "sultan/regal" identity without being garish. Text-only wordmark is cleanest for modern apps (Linear/Vercel pattern). No new dependencies — theme toggle via inline script + localStorage + CSS variables (existing system). Layout structure untouched: revamp = visual theme + branding, not architecture rewrite.

**What it will NOT do.**
- No layout restructure (component composition in page.tsx unchanged).
- No new dependencies (no next-themes, no Tailwind migration).
- No docker-compose container name changes (functional, not user-facing).
- No frontend/package.json name change (internal).
- No backend logic/pipeline changes.
- No new features.

**Effort.** ~5 todos + 4 parallel final checks. Mostly CSS variable swaps + component text edits.

**Risk.** Low. Main risks: theme toggle FOUC (mitigated by inline pre-paint script), gold-on-white contrast in light mode (mitigated by darker gold #B8860B), `background-clip: text` Safari prefix (mitigated by `-webkit-` prefix).

**Decisions.**
- Q1 theme: dark mode WITH toggle (dark default + light toggle)
- Q2 accent: gold regal modern clean (#D4A017 dark / #B8860B light)
- Q3 logo: text-only wordmark "Sultan Clip" (drop SVG mark)

## Scope

**In scope:**
1. Rewrite `frontend/app/globals.css` CSS variables: dark palette as default `:root`, light palette under `[data-theme="light"]`. Gold accent. Add theme toggle styles. Add gold gradient wordmark style.
2. Create `frontend/app/_components/ThemeToggle.tsx` — dark/light toggle using Sun/Moon icons from lucide-react, localStorage persistence, `data-theme` attribute on `<html>`.
3. Edit `frontend/app/layout.tsx` — add inline FOUC-prevention script in `<head>`, update metadata title to "Sultan Clip", update description.
4. Edit `frontend/app/_components/Topbar.tsx` — remove `<img>` logo mark, change `<h1>` to "Sultan Clip" with gold gradient class.
5. Edit `frontend/app/_components/SiteFooter.tsx` — strip Mallexibra/saweria/buy-me-coffee, replace with minimal copyright.
6. Edit `frontend/app/_components/ControlPanel.tsx` — placeholder "clipforge" → "sultanclip".
7. Create `frontend/public/favicon.svg` — gold "SC" monogram on dark rounded square.
8. Edit `frontend/public/logo.svg` — update title text (kept for backward compat, not used in header).
9. Edit `frontend/app/layout.tsx` — update favicon ref if needed.
10. Edit `backend/api.py` — `FastAPI(title="Sultan Clip API")`.
11. Edit `backend/clipper.py` — help text "clipforge" → "sultanclip".
12. Edit `backend/tests/test_hashtags.py` — test "clipforge" → "sultanclip".
13. Edit `frontend/README.md` — "# Sultan Clip Frontend".
14. Edit `README.md` (root) — "# ST Clippers" → "# Sultan Clip".
15. Edit `backend/README.md` — "# ST Clippers Backend" → "# Sultan Clip Backend".
16. Rebuild frontend container, visual QA dark + light mode.

**Out of scope:**
- Layout restructure, component composition changes.
- New dependencies (next-themes, Tailwind, etc.).
- docker-compose.yml container name changes.
- frontend/package.json name change.
- Backend logic/pipeline/API endpoint changes.
- New features.

## Verification strategy

All verification is agent-executed (zero user intervention):

| Check | Command | Expected |
|-------|---------|----------|
| No ClipForge refs | `grep -ri clipforge frontend/ backend/ --include="*.tsx" --include="*.ts" --include="*.py" --include="*.md"` | 0 matches |
| No Mallexibra refs | `grep -ri mallexibra frontend/ --include="*.tsx" --include="*.ts" --include="*.md"` | 0 matches |
| No saweria refs | `grep -ri saweria frontend/` | 0 matches |
| Topbar text | `grep -q "Sultan Clip" frontend/app/_components/Topbar.tsx` | exit 0 |
| No logo img in Topbar | `! grep -q 'src="/logo.svg"' frontend/app/_components/Topbar.tsx` | exit 0 |
| ThemeToggle exists | `test -f frontend/app/_components/ThemeToggle.tsx` | exit 0 |
| Gold accent in CSS | `grep -q "#D4A017" frontend/app/globals.css` | exit 0 |
| Dark vars in CSS | `grep -q "color-scheme: dark" frontend/app/globals.css` | exit 0 |
| Light theme override | `grep -q '\[data-theme="light"\]' frontend/app/globals.css` | exit 0 |
| Layout title | `grep -q 'title: "Sultan Clip"' frontend/app/layout.tsx` | exit 0 |
| Backend API title | `grep -q 'Sultan Clip API' backend/api.py` | exit 0 |
| Build passes | `docker compose exec frontend npm run build` or rebuild | exit 0 |
| Dark mode visual | screenshot of http://localhost:3000 in dark mode | gold wordmark, dark bg, clean panels |
| Light mode visual | screenshot after toggle click | gold wordmark, light bg, gold accents |
| Toggle works | curl page, check for ThemeToggle component + inline script | both present |

## Execution strategy

**Wave ordering:**
1. **Wave 1 (foundation):** globals.css dark theme + gold variables + ThemeToggle component + layout.tsx inline script. These are the foundation everything else sits on.
2. **Wave 2 (branding, parallel):** Topbar.tsx (wordmark), SiteFooter.tsx (strip identity), ControlPanel.tsx (placeholder), favicon.svg, logo.svg, backend files (api.py, clipper.py, test), README files. All independent files, dispatch in parallel.
3. **Wave 3 (verify):** Rebuild frontend container, run grep checks, visual QA dark + light.

**Rollback:** `git checkout -- .` discards all uncommitted changes. No database/state changes.

## Todos

- [x] 1. Rewrite globals.css dark theme + gold accent + ThemeToggle component + layout.tsx inline script
**References:**
- `frontend/app/globals.css` (1165 lines, CSS variables in `:root`, all components use `var(--*)`)
- `frontend/app/layout.tsx` (47 lines, metadata + Inter font + Toaster)
- Existing deps: `lucide-react` (Sun, Moon icons available), `react-hot-toast`
- No theme library installed — use inline script + localStorage + `data-theme` attr

**Steps:**
1. Edit `frontend/app/globals.css`:
   - Change `:root` to dark palette: `color-scheme: dark`, `--bg: #09090B`, `--panel: #18181B`, `--primary: #D4A017`, `--primary-hover: #B8860B`, `--text-primary: #FAFAFA`, `--text-secondary: #A1A1AA`, `--border: #27272A`, `--success: #22C55E`, `--warning: #F59E0B`, `--danger: #EF4444`. Keep `--shadow-sm`, `--shadow-md` (may need to darken for dark mode — use `rgb(0 0 0 / 0.3)` instead of `0.05`). Keep radius vars.
   - Add `[data-theme="light"]` block with light palette: `color-scheme: light`, `--bg: #F8FAFC`, `--panel: #FFFFFF`, `--primary: #B8860B`, `--primary-hover: #996F09`, `--text-primary: #0F172A`, `--text-secondary: #64748B`, `--border: #E2E8F0`, same success/warning/danger.
   - Update hardcoded colors that don't use vars: `.logBox background: #1E293B` (keep, it's a terminal-style log — works in both modes), `.topbar background: rgba(248,250,252,0.92)` → use `rgba(var(--bg-rgb), 0.92)` or just `var(--bg)` with opacity, `.segmentedControl background: #EEF2F7` → `var(--bg)`, `.field input background: #FFFFFF` → `var(--panel)`, `.fontSelect background: #FFFFFF` → `var(--panel)`, `.donationLink background: #FFFFFF` → remove (donation link being deleted).
   - Add `.wordmark` class for gold gradient text: `background: linear-gradient(135deg, #F0C040, #D4A017, #B8860B); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: transparent;`
   - Add `.themeToggle` button styles: `display: inline-grid; place-items: center; width: 40px; height: 40px; background: var(--panel); border: 1px solid var(--border); color: var(--text-secondary); border-radius: var(--radius-sm); cursor: pointer;` (reuse `.iconButton` pattern).
   - Add `:focus-visible` outline using gold: `outline-color: rgba(212, 160, 23, 0.35)`.

2. Create `frontend/app/_components/ThemeToggle.tsx`:
   ```tsx
   "use client";
   import { useEffect, useState } from "react";
   import { Moon, Sun } from "lucide-react";

   export function ThemeToggle() {
     const [theme, setTheme] = useState<"dark" | "light">("dark");

     useEffect(() => {
       const stored = localStorage.getItem("theme") as "dark" | "light" | null;
       if (stored) setTheme(stored);
     }, []);

     const toggle = () => {
       const next = theme === "dark" ? "light" : "dark";
       setTheme(next);
       localStorage.setItem("theme", next);
       document.documentElement.setAttribute("data-theme", next);
     };

     return (
       <button className="themeToggle iconButton" type="button" onClick={toggle} title="Toggle theme" aria-label="Toggle theme">
         {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
       </button>
     );
   }
   ```

3. Edit `frontend/app/layout.tsx`:
   - Add inline FOUC-prevention script in `<head>` (before children):
     ```tsx
     <head>
       <script dangerouslySetInnerHTML={{ __html: `
         (function() {
           try {
             var t = localStorage.getItem('theme') || 'dark';
             document.documentElement.setAttribute('data-theme', t);
           } catch(e) {
             document.documentElement.setAttribute('data-theme', 'dark');
           }
         })();
       `}} />
     </head>
     ```
   - Change `title: "ClipForge"` → `title: "Sultan Clip"`.
   - Change description to `"Turn long videos into ready-to-post clips"`.
   - Import and render `<ThemeToggle />` — but it needs to go in Topbar (next to refresh button), not layout. So just add the script + metadata here. ThemeToggle component is imported in Topbar.tsx (Wave 2).
   - Add `suppressHydrationWarning` to `<html>` tag (because inline script modifies `data-theme` before React hydrates).

**Acceptance criteria:**
- `grep -q "color-scheme: dark" frontend/app/globals.css` exit 0
- `grep -q '\[data-theme="light"\]' frontend/app/globals.css` exit 0
- `grep -q "#D4A017" frontend/app/globals.css` exit 0
- `grep -q "#B8860B" frontend/app/globals.css` exit 0
- `grep -q "background-clip: text" frontend/app/globals.css` exit 0
- `test -f frontend/app/_components/ThemeToggle.tsx` exit 0
- `grep -q "ThemeToggle" frontend/app/_components/ThemeToggle.tsx` exit 0
- `grep -q 'localStorage.getItem' frontend/app/_components/ThemeToggle.tsx` exit 0
- `grep -q 'data-theme' frontend/app/layout.tsx` exit 0
- `grep -q 'suppressHydrationWarning' frontend/app/layout.tsx` exit 0
- `grep -q 'title: "Sultan Clip"' frontend/app/layout.tsx` exit 0

**QA scenarios:**
- Happy: build passes, dark mode is default (no `data-theme` attr = `:root` dark), toggle switches to light.
- Failure A — FOUC: page flashes light then dark on load. Fix: verify inline script runs before paint (in `<head>`, before `<body>`).
- Failure B — toggle doesn't persist: refresh resets to dark. Fix: verify `localStorage.setItem` runs in toggle handler.
- Evidence: `.omo/verification/t1-theme.log`

**Commit:** `feat: dark theme foundation with gold accent + theme toggle`

---

- [x] 2. Rebrand Topbar + SiteFooter + ControlPanel + favicon + backend strings + READMEs (parallel batch)
**References:**
- `frontend/app/_components/Topbar.tsx` (22 lines)
- `frontend/app/_components/SiteFooter.tsx` (19 lines)
- `frontend/app/_components/ControlPanel.tsx` (line 474: placeholder)
- `frontend/public/favicon.svg` (16 lines)
- `frontend/public/logo.svg` (18 lines)
- `backend/api.py` (line 105)
- `backend/clipper.py` (line 1275)
- `backend/tests/test_hashtags.py` (line 5)
- `frontend/README.md` (line 1)
- `README.md` (root, line 1)
- `backend/README.md` (line 1)
- `frontend/app/_components/ThemeToggle.tsx` (created in T1)

**Steps (all independent files, edit in any order):**

1. Edit `frontend/app/_components/Topbar.tsx`:
   - Remove `<img className="brandMark" src="/logo.svg" alt="" aria-hidden="true" />` line.
   - Change `<h1 className="logo-text">ClipForge</h1>` → `<h1 className="logo-text wordmark">Sultan Clip</h1>`.
   - Import and add `<ThemeToggle />` next to refresh button:
     ```tsx
     import { RefreshCw } from "lucide-react";
     import { ThemeToggle } from "./ThemeToggle";
     // ...
     <ThemeToggle />
     <button className="iconButton" type="button" onClick={onRefresh} title="Refresh data">
       <RefreshCw size={18} />
     </button>
     ```

2. Edit `frontend/app/_components/SiteFooter.tsx`:
   - Replace entire content with minimal copyright:
     ```tsx
     export function SiteFooter() {
       return (
         <footer className="siteFooter">
           <p>© 2026 Sultan Clip</p>
         </footer>
       );
     }
     ```
   - Remove `Coffee, Heart` imports from lucide-react.

3. Edit `frontend/app/_components/ControlPanel.tsx`:
   - Line 474: `placeholder="clipforge, viral, fyp"` → `placeholder="sultanclip, viral, fyp"`.

4. Create new `frontend/public/favicon.svg`:
   ```svg
   <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
     <defs>
       <linearGradient id="gold" x1="14" y1="8" x2="50" y2="58" gradientUnits="userSpaceOnUse">
         <stop offset="0" stop-color="#F0C040"/>
         <stop offset="1" stop-color="#B8860B"/>
       </linearGradient>
     </defs>
     <rect x="6" y="6" width="52" height="52" rx="14" fill="#09090B"/>
     <text x="32" y="42" font-family="ui-sans-serif, system-ui, sans-serif" font-size="28" font-weight="800" fill="url(#gold)" text-anchor="middle">SC</text>
   </svg>
   ```

5. Edit `frontend/public/logo.svg`:
   - Change `<title id="title">ClipForge logo</title>` → `<title id="title">Sultan Clip logo</title>`.
   - Change `<desc>` text to "A gold play mark on dark background." (optional, kept for backward compat, not used in header).

6. Edit `backend/api.py`:
   - Line 105: `app = FastAPI(title="ClipForge API", version="0.1.0")` → `app = FastAPI(title="Sultan Clip API", version="0.1.0")`.

7. Edit `backend/clipper.py`:
   - Line 1275: `help="Comma-separated hashtags always appended to generated captions, e.g. clipforge,viral"` → `help="Comma-separated hashtags always appended to generated captions, e.g. sultanclip,viral"`.

8. Edit `backend/tests/test_hashtags.py`:
   - Line 5: `assert _normalize_hashtag("clipforge") == "#clipforge"` → `assert _normalize_hashtag("sultanclip") == "#sultanclip"`.

9. Edit `frontend/README.md`:
   - Line 1: `# ClipForge Frontend` → `# Sultan Clip Frontend`.
   - Line 3: `Next.js UI for running the local ClipForge backend.` → `Next.js UI for running the local Sultan Clip backend.`

10. Edit `README.md` (root):
    - Line 1: `# ST Clippers` → `# Sultan Clip`.
    - Author section: `Forked from [ClipForge]...` line — keep (attribution preserved per MIT), but update project name references.

11. Edit `backend/README.md`:
    - Line 1: `# ST Clippers Backend` → `# Sultan Clip Backend`.

**Acceptance criteria:**
- `grep -q "Sultan Clip" frontend/app/_components/Topbar.tsx` exit 0
- `! grep -q 'src="/logo.svg"' frontend/app/_components/Topbar.tsx` exit 0
- `grep -q "ThemeToggle" frontend/app/_components/Topbar.tsx` exit 0
- `! grep -qi mallexibra frontend/app/_components/SiteFooter.tsx` exit 0
- `! grep -qi saweria frontend/app/_components/SiteFooter.tsx` exit 0
- `! grep -qi "buy me a coffee" frontend/app/_components/SiteFooter.tsx` exit 0
- `grep -q "sultanclip" frontend/app/_components/ControlPanel.tsx` exit 0
- `! grep -q "clipforge" frontend/app/_components/ControlPanel.tsx` exit 0
- `grep -q "Sultan Clip" frontend/public/favicon.svg` (case-insensitive) — or `grep -qi "sc" frontend/public/favicon.svg` exit 0
- `grep -q "Sultan Clip API" backend/api.py` exit 0
- `grep -q "sultanclip" backend/clipper.py` exit 0
- `grep -q "sultanclip" backend/tests/test_hashtags.py` exit 0
- `grep -q "Sultan Clip Frontend" frontend/README.md` exit 0
- `grep -q "^# Sultan Clip$" README.md` exit 0
- `grep -q "Sultan Clip Backend" backend/README.md` exit 0

**QA scenarios:**
- Happy: all identity strings updated, no Mallexibra/saweria/buy-me-coffee remains.
- Failure A — missed a file: `grep -ri clipforge frontend/ backend/` returns matches. Fix each match.
- Evidence: `.omo/verification/t2-rebrand.log`

**Commit:** `feat: rebrand to Sultan Clip — strip upstream identity, gold wordmark, update all strings`

---

- [x] 3. Rebuild frontend container and verify build passes
**References:**
- Docker compose running from T2 (containers under old names `clipforge-*`, compose file has `st-clippers-*`).
- Frontend Dockerfile: `npm ci` + `npm run build` + `npm run start` (production server).
- Theme toggle uses `"use client"` + `localStorage` + `document.documentElement` — must work in SSR + client.

**Steps:**
1. Rebuild frontend container (pick up new CSS + components):
   ```bash
   cd "/Users/naufal/Documents/Sultan Tech/ST Clippers"
   docker compose --env-file .env up -d --build frontend 2>&1 | tee .omo/verification/t3-build.log
   ```

2. Wait for frontend ready (poll up to 60s):
   ```bash
   for i in $(seq 1 6); do
     sleep 10
     if curl -fsSI http://localhost:3000 2>/dev/null | head -1 | grep -q "200"; then echo "FRONTEND_READY"; break; fi
   done
   ```

3. Verify page renders with Sultan Clip title:
   ```bash
   curl -fsS http://localhost:3000 2>/dev/null | grep -qi "sultan clip" && echo "TITLE_OK" || echo "TITLE_FAIL"
   ```

4. Verify ThemeToggle component is in page HTML:
   ```bash
   curl -fsS http://localhost:3000 2>/dev/null | grep -qi "themeToggle\|Toggle theme" && echo "TOGGLE_OK" || echo "TOGGLE_FAIL"
   ```

5. Verify inline FOUC script is in page HTML:
   ```bash
   curl -fsS http://localhost:3000 2>/dev/null | grep -q "localStorage.getItem('theme')" && echo "FOUC_SCRIPT_OK" || echo "FOUC_SCRIPT_FAIL"
   ```

6. Verify no ClipForge in rendered HTML:
   ```bash
   curl -fsS http://localhost:3000 2>/dev/null | grep -qi clipforge && echo "CLIPFORGE_LEAK_FAIL" || echo "NO_CLIPFORGE_LEAK_PASS"
   ```

**Acceptance criteria:**
- `docker compose up -d --build frontend` exits 0 (build success)
- `curl -fsSI http://localhost:3000 | head -1` contains `200`
- `curl -fsS http://localhost:3000 | grep -qi "sultan clip"` exit 0
- `curl -fsS http://localhost:3000 | grep -qi "themeToggle\|Toggle theme"` exit 0
- `curl -fsS http://localhost:3000 | grep -q "localStorage.getItem('theme')"` exit 0
- `curl -fsS http://localhost:3000 | grep -qi clipforge` exit 1 (no matches)

**QA scenarios:**
- Happy: build passes, page renders, Sultan Clip title present, toggle present, no ClipForge leak.
- Failure A — build fails (TypeScript error in ThemeToggle): check build log, fix type error.
- Failure B — SSR hydration mismatch: `suppressHydrationWarning` on `<html>` tag should prevent this. If still failing, check inline script placement.
- Evidence: `.omo/verification/t3-build.log`, `.omo/verification/t3-render.log`

**Commit:** None (build only, no new commit — changes from T1+T2 already committed).

---

- [x] 4. Visual QA — dark mode + light mode screenshots
**References:**
- App running at http://localhost:3000 after T3 rebuild.
- Dark mode = default (no `data-theme` attr or `data-theme="dark"`).
- Light mode = `data-theme="light"` (via toggle click).
- Use browser screenshot tool (Playwright/agent-browser) to capture both states.

**Steps:**
1. Capture dark mode (default):
   ```bash
   # Use available browser screenshot tool. Playwright MCP or agent-browser.
   # Navigate to http://localhost:3000, take full-page screenshot.
   # Save to .omo/verification/t4-dark.png
   ```
   Verify visually: dark background (#09090B), gold "Sultan Clip" wordmark, gold accent on buttons/links, elevated panels (#18181B), clean spacing.

2. Capture light mode (after toggle):
   ```bash
   # Click theme toggle button (Sun icon in dark mode).
   # Take full-page screenshot.
   # Save to .omo/verification/t4-light.png
   ```
   Verify visually: light background (#F8FAFC), gold "Sultan Clip" wordmark, darker gold (#B8860B) accents, white panels, readable contrast.

3. Verify gold wordmark gradient:
   ```bash
   # In dark screenshot, confirm "Sultan Clip" text has gold gradient (not flat color).
   # In light screenshot, same gradient should be visible.
   ```

4. Verify footer stripped:
   ```bash
   # In both screenshots, footer should show only "© 2026 Sultan Clip" — no Mallexibra, no saweria, no buy-me-coffee.
   ```

**Acceptance criteria:**
- Dark screenshot exists at `.omo/verification/t4-dark.png`
- Light screenshot exists at `.omo/verification/t4-light.png`
- Dark screenshot: bg is dark (not white), wordmark is gold, no ClipForge text visible.
- Light screenshot: bg is light (not dark), wordmark is gold, no ClipForge text visible.
- Both screenshots: footer shows only copyright, no donation link.

**QA scenarios:**
- Happy: both screenshots captured, dark is dark, light is light, gold wordmark visible in both.
- Failure A — dark mode looks wrong (colors inverted, unreadable): check CSS variable values, check `color-scheme` property.
- Failure B — toggle doesn't work: check ThemeToggle component, check `data-theme` attribute switching.
- Failure C — gold wordmark invisible (transparent text): check `-webkit-text-fill-color: transparent` + `background-clip: text`.
- Evidence: `.omo/verification/t4-dark.png`, `.omo/verification/t4-light.png`

**Commit:** None (verification only).

---

## Final verification wave

Run all 4 in parallel. ALL must APPROVE.

- [x] F1. Identity cleanup audit
**Check:** `grep -ri clipforge frontend/ backend/ --include="*.tsx" --include="*.ts" --include="*.py" --include="*.md" --include="*.svg"` returns 0 matches. `grep -ri mallexibra frontend/` returns 0 matches. `grep -ri saweria frontend/` returns 0 matches. `grep -ri "buy me a coffee" frontend/` returns 0 matches.
**Evidence:** `.omo/verification/f1-identity.log`

- [x] F2. Theme + gold accent CSS audit
**Check:** `grep -q "color-scheme: dark" frontend/app/globals.css`, `grep -q '\[data-theme="light"\]' frontend/app/globals.css`, `grep -q "#D4A017" frontend/app/globals.css`, `grep -q "#B8860B" frontend/app/globals.css`, `grep -q "background-clip: text" frontend/app/globals.css`. All exit 0.
**Evidence:** `.omo/verification/f2-css.log`

- [x] F3. Build + render verification
**Check:** `docker compose ps frontend` shows Up. `curl -fsS http://localhost:3000 | grep -qi "sultan clip"` exit 0. `curl -fsS http://localhost:3000 | grep -qi clipforge` exit 1. `curl -fsS http://localhost:3000 | grep -q "localStorage.getItem('theme')"` exit 0.
**Evidence:** `.omo/verification/f3-render.log`

- [x] F4. Scope fidelity audit
**Check:** `git diff --stat` shows only expected files (globals.css, ThemeToggle.tsx, layout.tsx, Topbar.tsx, SiteFooter.tsx, ControlPanel.tsx, favicon.svg, logo.svg, api.py, clipper.py, test_hashtags.py, frontend/README.md, README.md, backend/README.md). No docker-compose.yml, no package.json, no page.tsx, no component composition changes.
**Evidence:** `.omo/verification/f4-scope.log`

## Commit strategy

Two commits:
1. `feat: dark theme foundation with gold accent + theme toggle` (T1 — globals.css, ThemeToggle.tsx, layout.tsx)
2. `feat: rebrand to Sultan Clip — strip upstream identity, gold wordmark, update all strings` (T2 — all branding files)

T3 and T4 are verification only (no commits).

## Success criteria

Plan is complete when ALL of the following are true:
1. T1-T4 acceptance criteria all pass (F1 approves).
2. Zero ClipForge/Mallexibra/saweria/buy-me-coffee references in frontend + backend source (F1 approves).
3. Dark mode is default, light mode toggle works, gold accent throughout (F2 approves).
4. Frontend container rebuilt, page renders with "Sultan Clip", no ClipForge leak in HTML (F3 approves).
5. Diff stat shows only expected files, no scope creep (F4 approves).
6. Visual QA screenshots captured for both dark + light mode (T4 passes).
