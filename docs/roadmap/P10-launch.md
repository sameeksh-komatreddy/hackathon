# P10 Launch

## S26 Retire Python and deploy
- Move `backend_pm.py`, `cameras.py`, `phone_link.py`, `screen_distance.py`, `frontend_pm.html`, `requirements.txt` and `tests/` into `legacy/`. Drop pytest from CI.
- Move `web/` to the repo root (optional).
- Rewrite the README: what it does, a link to the live site, privacy summary, local development (`npm i && npm run dev`), supported browsers.
- Production deploy. Tag `v1.0.0`.
- **Done when:** the live URL works for someone who has never seen the project.

## S27 ★ Beta and feedback
- 5–10 real users for a week. Free feedback channel: GitHub Issues template or a Google Form linked from Settings.
- Watch for: false alerts (tune the default thresholds), calibration confusion, browsers dropping data, notification permission problems.
- Turn the findings into a short list of fix sessions added to the ROADMAP.
