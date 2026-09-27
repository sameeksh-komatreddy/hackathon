# P0–P1 Cleanup and foundation

## S01 Repo cleanup
- Move `backend_hr_V1`, `backend_hra`, `backend_hres`, `backend_vinayak_is_a_bum.py`, `frontend_hr_V1.html`, `frontend_hra.html`, `frontend_hres.html`, `frontend_vinayak_is_a_bum.html` and `original_*` into `legacy/` using `git mv`.
- Remove `.DS_Store` and `.vscode/launch.json` from git; add `.vscode/` to `.gitignore`. Delete the unused `SECRET_KEY` (U8).
- README: finish the cut-off sentence (U6), and correct the lighting (U4) and trend-notification (U5) claims.
- ★ Choose a license (ask the user; MIT is the usual default).
- **Done when:** the repo root holds only current files and the tests still pass.

## S02a ★ React scaffold and static layout
- `npm create vite@latest web -- --template react` (D4). The app lives in `web/`; the Python code stays at the root until S26.
- Move the CSS from `frontend_pm.html` to `web/src/styles.css` as it is, keeping the class names. Build components under `web/src/ui/` for the markup: `App`, `Sidebar`, `Toast`, `TrendChart`, and one per tab (`HistoryTab`, `RecordTab`, `ExportTab`, `SettingsTab`). Create `core/` and `storage/` empty for now.
- Tabs are React state (no router). `/phone` becomes a second Vite entry page in S18.
- Add Vitest with React Testing Library, and one render test.
- **Done when:** all four tabs render and look like the old page (no data yet), and `npm test` passes.

## S02b ⚙ Hook the React UI up to the Python backend
- Port the event handlers and `fetch` calls from `frontend_pm.html` into the components, grepping the old file by section comment (`/* ==== … ==== */`). Keep state in `useState`/`useReducer`, with one context for the signed-in user and settings. No state library.
- Put every backend call in `web/src/api.ts`, so P5 can swap it for `storage/repo.ts` in one place.
- The Python backend must accept the Vite dev origin. (Already true: `LOCAL_ORIGIN` allows any localhost port.)
- **Done when:** `npm run dev` does everything the old page did against the Python backend.

## S03 ★ CI and deploy
- GitHub Actions workflow: run `pytest` (until S23) and `npm ci && npm test && npm run build` in `web/`.
- Connect the repo to Cloudflare Pages: build `npm run build`, root `web`, output `dist`. Every branch gets a preview URL. Free subdomain `*.pages.dev`; a custom domain is optional and costs money.
- **Done when:** a push to `main` deploys, and a pull request gets a preview link.
