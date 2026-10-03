# BackTrack production roadmap

Goal: turn BackTrack into a free, browser-only web app. Tracking runs in the browser, data stays on the device (IndexedDB), and insights come from a premade response library instead of an AI API. Running cost: $0.

## How to use this in a session

1. Read this file. Find the first unchecked session below.
2. Read **only** that session's phase file, plus any audit IDs it cites in [AUDIT.md](AUDIT.md).
3. Stop when the session's "Done when" line is met. Run the tests, then commit.
4. Tick the box and add one line to the progress log (keep only the last 10 entries).

Keeping each session within a Pro plan usage window:
- Start with a fresh context (`/clear`).
- Don't open the `legacy/` files or `frontend_pm.html` in full; grep for what you need.
- Use a lighter model for mechanical porting sessions (marked ⚙).

## Decisions

| # | Decision | Status |
|---|----------|--------|
| D1 | No app server. Static site as a Cloudflare Worker with static assets (free and unlimited asset requests, works with private repos). Chosen over Pages, which Cloudflare now labels legacy | Agreed |
| D2 | All data local in IndexedDB. No accounts or passwords; optional local profiles | Agreed |
| D3 | Premade insight library replaces Gemini ([P6](roadmap/P6-insights.md)) | Agreed |
| D4 | Vite + React + TypeScript for the UI. `core/` and `storage/` stay plain modules with no React imports | Agreed |
| D5 | Fix legacy bugs while porting, not in the Python app. Keep the Python backend as a reference until P3 is done, then archive it | Agreed |
| D6 | Phone camera ships at launch as a WebRTC video stream, paired through a free Cloudflare Worker ([P7](roadmap/P7-phone.md)) | Agreed |
| D7 | Lighting check and screen distance come after launch ([P11](roadmap/P11-post-launch.md)) | Proposed |

★ = a step that wasn't in the original audit but is needed for production.

## Sessions

**[P0–P1 Cleanup and foundation](roadmap/P0-P1-foundation.md)**
- [x] S01 Repo cleanup: archive old iterations, fix the README
- [x] S02a ★ React scaffold and static layout
- [x] S02b ⚙ Hook the React UI up to the Python backend
- [ ] S03 ★ CI (tests and build) and Cloudflare Workers deploy. **Paused:** CI and `web/wrangler.jsonc` are done. Waiting for Sameeksh to move the repo into a GitHub organization with anshulfs as owner (a collaborator can't connect a personal repo to Cloudflare). Then: update the git remote, connect Workers Builds (settings in the phase file), and check a PR preview link. S04 goes first meanwhile.

**[P2 Feasibility check](roadmap/P2-spike.md)** (go/no-go gate)
- [ ] S04 ★ MediaPipe in the browser: frame rate, background-tab behaviour, Safari/Firefox

**[P3 Detection port](roadmap/P3-detection.md)**
- [ ] S05 ⚙ Port the scoring and metric math, with tests
- [ ] S06 Tracking loops for the front and side cameras
- [ ] S07 ★ Guided calibration and browser camera picker
- [ ] S08 Alert engine that only runs while recording, plus quiet hours

**[P4 Local storage](roadmap/P4-storage.md)**
- [ ] S09 IndexedDB schema v1 and data layer, with tests
- [ ] S10 ★ Persistent storage, backup export/import, crash checkpointing

**[P5 UI on local data](roadmap/P5-ui.md)**
- [ ] S11 Record tab
- [ ] S12 History and Settings tabs (with a real dark theme)
- [ ] S13 ⚙ Export tab: PDF generated in the browser

**[P6 Premade insights](roadmap/P6-insights.md)**
- [ ] S14 Pattern classifier, with tests
- [ ] S15 Write the response library
- [ ] S16 Wire it into History and the PDF; remove Gemini

**[P7 Phone camera](roadmap/P7-phone.md)**
- [ ] S17 ★ Signalling Worker and QR pairing
- [ ] S18 Phone page streaming into a camera slot
- [ ] S19 ★ Connections across real networks (STUN/TURN, test matrix)

**[P8 Notifications and offline](roadmap/P8-pwa.md)**
- [ ] S20 Browser notifications and permission flow
- [ ] S21 ★ Service worker, offline model cache, installable app

**[P9 Production hardening](roadmap/P9-hardening.md)**
- [ ] S22 ★ Privacy policy, health disclaimer, first-run consent
- [ ] S23 ★ Security headers, self-hosted models, dependency audit
- [ ] S24 ★ Accessibility, responsive layout, cross-browser pass
- [ ] S25 ★ Performance tuning and end-to-end smoke test in CI

**[P10 Launch](roadmap/P10-launch.md)**
- [ ] S26 Retire the Python backend; final README; production deploy
- [ ] S27 ★ Small beta and a feedback channel

**[P11 After launch](roadmap/P11-post-launch.md)** (optional): lighting check, screen distance

## Progress log

_(newest first; keep 10)_

- 2026-10-03 S03 (paused): CI workflow passing (pytest + web test/build); deploy target switched from Pages to Workers (D1); Cloudflare connect blocked until the repo moves to an org; doing S04 first

- 2026-09-27 S02b: React UI wired to the Python backend through web/src/api.ts; checked live end to end (backend in a .venv, Python 3.12). Fixed while porting: AI Refresh no longer recalibrates the side camera, sign-out stops a running session, reload resumes a running session, threshold hint stays 4 s, export dates use local time, late alert no longer hides the "Session saved" toast

- 2026-09-27 S02a: web/ Vite + React + TypeScript app, CSS copied as is, login + 4 tabs as components, Vitest render tests; login kept until local profiles replace it

- 2026-09-27 S01: old iterations moved to legacy/, clutter untracked, SECRET_KEY removed, README fixed; no license (owner choice)
