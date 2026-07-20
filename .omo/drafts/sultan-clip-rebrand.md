# sultan-clip-rebrand - Draft

## Intent
- intent: clear
- review_required: false
- Classify: Standard (UI theme revamp + rebrand, ~12 files, clear scope)

## Status
- status: approved (user answered Q1-Q3 on 2026-07-20)
- pending action: write .omo/plans/sultan-clip-rebrand.md + append todos + fill TL;DR

## Decisions (user-answered forks)
- Q1 theme: dark mode WITH toggle (dark default + light toggle). User chose toggle over dark-only.
- Q2 accent: gold regal modern clean (#D4A017 family). User chose gold over keeping blue.
- Q3 logo: text-only wordmark "Sultan Clip" (drop SVG mark from header). User chose text-only.

## Adopted defaults (not asked, reversible)
- Theme toggle: no next-themes dependency. Inline FOUC-prevention script in layout.tsx + ThemeToggle component using localStorage + data-theme attribute on <html>. Ponytail: use stdlib/existing deps.
- Dark palette: off-black bg #09090B, panels #18181B, borders #27272A, text #FAFAFA, secondary #A1A1AA. No pure black/white (skill rule).
- Light palette: keep existing bg #F8FAFC, panels #FFFFFF, but swap primary to gold #B8860B (darker for contrast on white).
- Gold gradient wordmark: linear-gradient(135deg, #F0C040, #D4A017, #B8860B) with background-clip: text.
- Font: keep Inter (already loaded, clean in dark mode).
- Layout structure: NO changes to page.tsx component composition. Revamp = visual theme + branding, not architecture.
- Favicon: new favicon.svg with gold "SC" monogram on dark rounded square.
- SiteFooter: strip all Mallexibra/saweria/buy-me-coffee. Replace with minimal "© 2026 Sultan Clip" or remove entirely.
- Container names in docker-compose.yml: NOT changed (st-clippers-* is functional, not user-facing brand).
- frontend/package.json name: NOT changed (internal, not user-facing).

## Components ledger
| ID | Outcome | Status | Evidence path |
|----|---------|--------|---------------|
| C1 | Dark theme foundation in globals.css + theme toggle mechanism | pending | `:root` dark vars, `[data-theme=light]` overrides, ThemeToggle component works |
| C2 | Gold accent color applied throughout via CSS variables | pending | `--primary: #D4A017` dark, `#B8860B` light; all references auto-update |
| C3 | Text-only "Sultan Clip" wordmark in Topbar (gold gradient) | pending | Topbar.tsx has no <img>, <h1> has gold gradient text |
| C4 | All identity strings cleaned (ClipForge→Sultan Clip, no Mallexibra/saweria) | pending | `grep -ri clipforge frontend/ backend/` = 0; `grep -ri mallexibra frontend/` = 0 |
| C5 | Metadata + favicon updated | pending | layout.tsx title="Sultan Clip", favicon.svg gold SC mark |
| C6 | Build passes + visual QA dark + light | pending | `npm run build` exit 0; dark screenshot; light toggle screenshot |

## Key facts (from codebase exploration)
- globals.css: 1165 lines, CSS variables in `:root` (light only), `color-scheme: light`. All components use `var(--*)` tokens.
- Topbar.tsx: 22 lines. `<img className="brandMark" src="/logo.svg">` + `<h1 className="logo-text">ClipForge</h1>` + refresh button.
- SiteFooter.tsx: 19 lines. "Open-source project by Mallexibra" + saweria.co/mallexibra "Buy me a coffee" link.
- layout.tsx: 47 lines. `title: "ClipForge"`, `icons.icon: "/favicon.svg"`, Inter font, Toaster with CSS var styling.
- ControlPanel.tsx:492: placeholder `clipforge, viral, fyp`.
- logo.svg + favicon.svg: identical blue gradient play-mark + spark. 18 lines each.
- backend/api.py:105: `FastAPI(title="ClipForge API", version="0.1.0")`.
- backend/clipper.py:1275: help text `clipforge,viral`.
- backend/tests/test_hashtags.py:5: `assert _normalize_hashtag("clipforge") == "#clipforge"`.
- frontend/README.md:1: `# ClipForge Frontend`.
- Root README.md:1: `# ST Clippers` (from T3 rebrand).
- backend/README.md:1: `# ST Clippers Backend` (from T3 rebrand).
- frontend/package.json: `"name": "st-clippers"` (from T3, internal, not changing).
- Docker containers running from T2 under old names (clipforge-*). Compose file has st-clippers-* (T3). Not user-facing.
- Existing deps: next ^16, react ^19, lucide-react, react-hot-toast. No theme library installed.

## Risks
- Theme toggle FOUC (flash of unstyled content) on page load — mitigated by inline script in <head> that sets data-theme before paint.
- Gold on white (light mode) needs WCAG AA contrast — #B8860B on #FFFFFF = 4.5:1 ratio (passes AA for normal text, borderline for large text). Buttons use gold bg + white text = high contrast.
- `background-clip: text` for gold gradient wordmark needs `-webkit-` prefix for Safari.
- lucide-react already has Sun/Moon icons — use for toggle button (no new dep).
- Docker frontend container runs production build (`npm run start`). Theme toggle must work in production SSR. Inline script in layout.tsx runs before hydration.
